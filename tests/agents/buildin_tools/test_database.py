import json
import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from openbot.agents.buildin_tools.database import (
    CustomJSONEncoder,
    SQLiteTool,
)


class TestCustomJSONEncoder:
    def test_datetime_serialization(self):
        test_dt = datetime(2024, 1, 1, 12, 0, 0)
        result = json.dumps({"dt": test_dt}, cls=CustomJSONEncoder)
        assert json.loads(result)["dt"] == "2024-01-01T12:00:00"

    def test_date_serialization(self):
        test_date = date(2024, 1, 1)
        result = json.dumps({"date": test_date}, cls=CustomJSONEncoder)
        assert json.loads(result)["date"] == "2024-01-01"

    def test_decimal_serialization(self):
        test_decimal = Decimal("123.45")
        result = json.dumps({"num": test_decimal}, cls=CustomJSONEncoder)
        assert json.loads(result)["num"] == 123.45

    def test_default_types(self):
        test_data = {"str": "test", "int": 123, "float": 1.23, "bool": True, "null": None}
        result = json.dumps(test_data, cls=CustomJSONEncoder)
        assert json.loads(result) == test_data


class TestSQLiteTool:
    @pytest.fixture
    async def sqlite_tool(self):
        tool = SQLiteTool()
        await tool.connect(":memory:", readonly=False)
        # 创建测试表
        await tool.execute_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, created_at DATETIME)")
        await tool.execute_sql("INSERT INTO users (name, age, created_at) VALUES (:name, :age, :created_at)", 
                              {"name": "Alice", "age": 25, "created_at": datetime(2024, 1, 1)})
        await tool.execute_sql("INSERT INTO users (name, age, created_at) VALUES (:name, :age, :created_at)", 
                              {"name": "Bob", "age": 30, "created_at": datetime(2024, 1, 2)})
        yield tool
        await tool.close()

    def test_check_sql_security_empty_sql(self):
        tool = SQLiteTool()
        with pytest.raises(ValueError, match="SQL 语句不能为空"):
            tool._check_sql_security("")
        with pytest.raises(ValueError, match="SQL 语句不能为空"):
            tool._check_sql_security("   ")
        with pytest.raises(ValueError, match="SQL 语句不能为空"):
            tool._check_sql_security("-- comment\n/* comment */")

    def test_check_sql_security_forbidden_keywords(self):
        tool = SQLiteTool()
        forbidden_cases = [
            "DROP TABLE users",
            "drop table users",
            "TRUNCATE users",
            "ALTER TABLE users ADD COLUMN email TEXT",
            "GRANT ALL ON users TO test",
            "REVOKE ALL ON users FROM test",
            "SHUTDOWN",
            "DETACH DATABASE test",
            "SELECT * FROM users; DROP TABLE users",
        ]
        for sql in forbidden_cases:
            with pytest.raises(ValueError, match="安全风险：检测到禁止使用的关键词"):
                tool._check_sql_security(sql)

    def test_check_sql_security_readonly_mode(self):
        tool = SQLiteTool()
        tool.readonly = True
        
        # 允许的语句
        allowed_cases = [
            "SELECT * FROM users",
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte",
            "SHOW TABLES",
            "DESC users",
            "EXPLAIN SELECT * FROM users",
            "PRAGMA table_info(users)",
        ]
        for sql in allowed_cases:
            tool._check_sql_security(sql)  # 不抛出异常
        
        # 禁止的语句
        forbidden_cases = [
            "INSERT INTO users (name) VALUES ('Charlie')",
            "UPDATE users SET age = 26 WHERE id = 1",
            "DELETE FROM users WHERE id = 1",
            "CREATE TABLE test (id INTEGER)",
        ]
        for sql in forbidden_cases:
            with pytest.raises(ValueError, match="安全限制：当前处于只读模式"):
                tool._check_sql_security(sql)

    def test_check_sql_security_non_readonly_mode(self):
        tool = SQLiteTool()
        tool.readonly = False
        
        # 允许非查询语句（除了黑名单关键词）
        allowed_cases = [
            "INSERT INTO users (name) VALUES ('Charlie')",
            "UPDATE users SET age = 26 WHERE id = 1",
            "DELETE FROM users WHERE id = 1",
            "CREATE TABLE test (id INTEGER)",
        ]
        for sql in allowed_cases:
            tool._check_sql_security(sql)  # 不抛出异常

    @pytest.mark.asyncio
    async def test_connect_memory_database(self):
        tool = SQLiteTool()
        response = await tool.connect(":memory:")
        assert response.content[0]["type"] == "text"
        assert "数据库连接成功" in response.content[0]["text"]
        assert tool.engine is not None
        await tool.close()

    @pytest.mark.asyncio
    async def test_connect_file_path(self, tmp_path):
        db_path = tmp_path / "test.db"
        tool = SQLiteTool()
        response = await tool.connect(str(db_path))
        assert "数据库连接成功" in response.content[0]["text"]
        assert tool.db_url == f"sqlite+aiosqlite:///{str(db_path)}"
        await tool.close()

    @pytest.mark.asyncio
    async def test_connect_with_already_sqlite_url(self):
        tool = SQLiteTool()
        response = await tool.connect("sqlite:///test.db")
        assert tool.db_url == "sqlite+aiosqlite:///test.db"
        await tool.close()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        tool = SQLiteTool()
        with patch("openbot.agents.buildin_tools.database.create_async_engine", side_effect=Exception("Connection error")):
            response = await tool.connect(":memory:")
            assert "连接数据库失败: Connection error" in response.content[0]["text"]
            assert tool.engine is None

    @pytest.mark.asyncio
    async def test_list_tables_not_connected(self):
        tool = SQLiteTool()
        response = await tool.list_tables()
        assert "无法获取表列表: 数据库引擎未初始化，请先调用 connect 方法" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_tables_success(self, sqlite_tool):
        response = await sqlite_tool.list_tables()
        assert "数据库中包含 1 个表: users" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_get_table_info_not_connected(self):
        tool = SQLiteTool()
        response = await tool.get_table_info("users")
        assert "无法获取表 'users' 的结构信息: 数据库引擎未初始化，请先调用 connect 方法" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_get_table_info_not_exists(self, sqlite_tool):
        response = await sqlite_tool.get_table_info("non_existent_table")
        assert "无法获取表 'non_existent_table' 的结构信息:" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_get_table_info_success(self, sqlite_tool):
        response = await sqlite_tool.get_table_info("users")
        content = response.content[0]["text"]
        assert "表 users 结构信息:" in content
        assert "列数: 4" in content
        assert "主键: ['id']" in content
        assert "索引数: 0" in content
        assert "name" in content
        assert "age" in content
        assert "created_at" in content

    @pytest.mark.asyncio
    async def test_execute_sql_not_connected(self):
        tool = SQLiteTool()
        response = await tool.execute_sql("SELECT * FROM users")
        assert "错误: 数据库执行异常" in response.content[0]["text"]
        assert "数据库引擎未初始化，请先调用 connect 方法" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_execute_sql_security_error(self, sqlite_tool):
        response = await sqlite_tool.execute_sql("DROP TABLE users")
        assert "错误: SQL 安全拒绝: 安全风险：检测到禁止使用的关键词 'DROP'" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_execute_sql_select_success(self, sqlite_tool):
        response = await sqlite_tool.execute_sql("SELECT * FROM users ORDER BY id")
        data = json.loads(response.content[0]["text"])
        assert len(data) == 2
        assert data[0]["name"] == "Alice"
        assert data[0]["age"] == 25
        assert data[1]["name"] == "Bob"
        assert data[1]["age"] == 30

    @pytest.mark.asyncio
    async def test_execute_sql_select_with_params(self, sqlite_tool):
        response = await sqlite_tool.execute_sql(
            "SELECT * FROM users WHERE age > :age",
            {"age": 25}
        )
        data = json.loads(response.content[0]["text"])
        assert len(data) == 1
        assert data[0]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_execute_sql_max_rows_limit(self, sqlite_tool):
        # 插入更多测试数据
        for i in range(10):
            await sqlite_tool.execute_sql(
                "INSERT INTO users (name, age) VALUES (:name, :age)",
                {"name": f"User{i}", "age": 20 + i}
            )
        
        # 限制返回3行
        response = await sqlite_tool.execute_sql("SELECT * FROM users", max_rows=3)
        data = json.loads(response.content[0]["text"])
        assert len(data) == 3

        # 使用默认限制
        sqlite_tool.max_rows_limit = 5
        response = await sqlite_tool.execute_sql("SELECT * FROM users")
        data = json.loads(response.content[0]["text"])
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_execute_sql_dml_operation(self, sqlite_tool):
        # 插入数据
        insert_resp = await sqlite_tool.execute_sql(
            "INSERT INTO users (name, age) VALUES (:name, :age)",
            {"name": "Charlie", "age": 35}
        )
        assert "执行成功，影响 1 行" in insert_resp.content[0]["text"]

        # 验证插入
        select_resp = await sqlite_tool.execute_sql("SELECT * FROM users WHERE name = 'Charlie'")
        data = json.loads(select_resp.content[0]["text"])
        assert len(data) == 1
        assert data[0]["age"] == 35

        # 更新数据
        update_resp = await sqlite_tool.execute_sql(
            "UPDATE users SET age = :age WHERE name = :name",
            {"name": "Charlie", "age": 36}
        )
        assert "执行成功，影响 1 行" in update_resp.content[0]["text"]

        # 删除数据
        delete_resp = await sqlite_tool.execute_sql(
            "DELETE FROM users WHERE name = :name",
            {"name": "Charlie"}
        )
        assert "执行成功，影响 1 行" in delete_resp.content[0]["text"]

    @pytest.mark.asyncio
    async def test_execute_sql_syntax_error(self, sqlite_tool):
        response = await sqlite_tool.execute_sql("SELECT * FROM non_existent_table")
        assert "错误: 数据库执行异常" in response.content[0]["text"]
        assert "no such table: non_existent_table" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_execute_sql_readonly_mode(self, sqlite_tool):
        # 切换到只读模式
        sqlite_tool.readonly = True
        response = await sqlite_tool.execute_sql("INSERT INTO users (name, age) VALUES ('Dave', 40)")
        assert "错误: SQL 安全拒绝: 安全限制：当前处于只读模式" in response.content[0]["text"]

    @pytest.mark.asyncio
    async def test_close(self, sqlite_tool):
        assert sqlite_tool.engine is not None
        await sqlite_tool.close()
        assert sqlite_tool.engine is None

        # 多次调用close不报错
        await sqlite_tool.close()
        assert sqlite_tool.engine is None
