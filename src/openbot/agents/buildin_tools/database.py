"""
异步数据库操作类，提供查看表、获取表结构和执行 SQL 的功能。
支持多种异步驱动（如 aiosqlite, aiomysql, asyncpg 等）。
包含基础的安全审计和执行限制。
"""

import json
import logging
import re
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Union, Sequence
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


class CustomJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理日期、小数等特殊类型"""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class SQLiteTool:
    """
    异步数据库操作类，提供查看表、获取表结构和执行 SQL 的功能。
    支持多种异步驱动（如 aiosqlite, aiomysql, asyncpg 等）。
    包含基础的安全审计和执行限制。
    """

    # 危险操作黑名单（不分大小写）
    FORBIDDEN_KEYWORDS = {
        "DROP",
        "TRUNCATE",
        "ALTER",
        "GRANT",
        "REVOKE",
        "SHUTDOWN",
        "DETACH",
    }

    def __init__(self):
        """
        初始化异步数据库连接。
        """
        self.db_url = ""
        self.readonly = True
        self.max_rows_limit = 1000
        self.engine: Optional[AsyncEngine] = None

    def _check_sql_security(self, sql: str) -> None:
        """
        简单的 SQL 安全审计。
        """
        # 移除 SQL 注释，防止通过注释绕过检查
        clean_sql = re.sub(r"--.*?\n|/\*.*?\*/", "", sql, flags=re.DOTALL).strip()
        upper_sql = clean_sql.upper()

        if not upper_sql:
            raise ValueError("SQL 语句不能为空")

        # 1. 检查危险关键词
        for keyword in self.FORBIDDEN_KEYWORDS:
            if keyword in upper_sql:
                raise ValueError(f"安全风险：检测到禁止使用的关键词 '{keyword}'")

        # 2. 如果是只读模式，检查是否包含非查询操作
        if self.readonly:
            # 只允许以 SELECT, WITH, PRAGMA (部分), SHOW 等开头的语句
            allowed_starts = ("SELECT", "WITH", "SHOW", "DESC", "EXPLAIN", "PRAGMA")
            if not any(upper_sql.startswith(start) for start in allowed_starts):
                raise ValueError(
                    "安全限制：当前处于只读模式，仅支持查询类操作 (SELECT/WITH 等)"
                )

    async def connect(
        self,
        db_path: str = ":memory:",
        readonly: bool = True,
        max_rows_limit: int = 1000,
    ) -> ToolResponse:
        """
        异步连接数据库。
        参数:
            db_path (str): 数据库路径，默认 ":memory:" 为内存数据库。
            readonly (bool): 是否只读模式，默认 True。
            max_rows_limit (int): 最大返回行数限制，默认 1000。
        返回:
            ToolResponse: 包含连接结果的响应对象。
        """
        try:
            # 确保如果是 sqlite，使用的是 aiosqlite 驱动
            if db_path.startswith("sqlite://") and "aiosqlite" not in db_path:
                db_url = db_path.replace("sqlite://", "sqlite+aiosqlite://")
            else:
                db_url = f"sqlite+aiosqlite:///{db_path}"

            self.db_url = db_url
            self.readonly = readonly
            self.max_rows_limit = max_rows_limit
            self.engine = create_async_engine(db_url)
            return ToolResponse(content=[TextBlock(type="text", text="数据库连接成功")])
        except Exception as e:
            logging.error(f"连接数据库失败: {e}")
            return ToolResponse(
                content=[TextBlock(type="text", text=f"连接数据库失败: {str(e)}")]
            )

    async def list_tables(self) -> ToolResponse:
        """
        异步列出数据库中所有的表名。

        注意：
          使用前先调用 connect 方法连接数据库。

        返回:
            ToolResponse: 包含表名列表的响应对象。
        """

        try:
            if not self.engine:
                raise ValueError("数据库引擎未初始化，请先调用 connect 方法")

            async with self.engine.connect() as conn:
                tables = await conn.run_sync(
                    lambda sync_conn: inspect(sync_conn).get_table_names()
                )
                logging.info(f"成功获取 {len(tables)} 个表")
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=f"数据库中包含 {len(tables)} 个表: {', '.join(tables)}",
                        )
                    ]
                )
        except Exception as e:
            logging.error(f"列出表失败: {e}")
            return ToolResponse(
                content=[TextBlock(type="text", text=f"无法获取表列表: {str(e)}")]
            )

    async def get_table_info(self, table_name: str) -> ToolResponse:
        """
        异步获取指定表的结构信息。

        参数:
            table_name (str): 要获取结构信息的表名。

        注意：
          使用前先调用 connect 方法连接数据库。

        返回:
            ToolResponse: 包含表结构信息的响应对象。
        """
        try:
            if not self.engine:
                raise ValueError("数据库引擎未初始化，请先调用 connect 方法")

            async with self.engine.connect() as conn:

                def _get_info(sync_conn):
                    ins = inspect(sync_conn)
                    columns = ins.get_columns(table_name)
                    pk = ins.get_pk_constraint(table_name)
                    indexes = ins.get_indexes(table_name)
                    return columns, pk, indexes

                columns, pk, indexes = await conn.run_sync(_get_info)

                formatted_columns = [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col["nullable"],
                        "default": str(col["default"]) if col["default"] else None,
                    }
                    for col in columns
                ]

                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=f"表 {table_name} 结构信息:\n"
                            f"列数: {len(formatted_columns)}\n"
                            f"主键: {pk.get('constrained_columns', [])}\n"
                            f"索引数: {len(indexes)}\n"
                            f"列详情: {json.dumps(formatted_columns, cls=CustomJSONEncoder)}",
                        )
                    ]
                )

        except Exception as e:
            logging.error(f"获取表 {table_name} 信息失败: {e}")
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"无法获取表 '{table_name}' 的结构信息: {str(e)}",
                    )
                ]
            )

    async def execute_sql(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        max_rows: Optional[int] = None,
    ) -> ToolResponse:
        """
        异步执行自定义 SQL 语句并返回结果。

        参数:
            sql (str): 要执行的 SQL 语句。
            params (Optional[Dict[str, Any]]): SQL 语句中的参数，默认 None。
            max_rows (Optional[int]): 最大返回行数，默认 None。

        注意：
          使用前先调用 connect 方法连接数据库。

        返回:
            ToolResponse: 包含执行结果的响应对象。
        """
        try:
            if not self.engine:
                raise ValueError("数据库引擎未初始化，请先调用 connect 方法")

            # 1. 运行安全审计
            self._check_sql_security(sql)

            async with self.engine.connect() as conn:
                # 2. 执行查询
                result = await conn.execute(text(sql), params or {})

                if result.returns_rows:
                    # 3. 强制限制返回行数，防止内存溢出
                    limit = max_rows or self.max_rows_limit
                    rows = result.fetchmany(limit)

                    if len(rows) >= limit:
                        logging.warning(
                            f"查询结果达到行数上限 ({limit})，结果已被截断。"
                        )

                    # 使用自定义编码器处理特殊类型
                    ret_json = json.dumps(
                        [dict(row._mapping) for row in rows],
                        indent=4,
                        cls=CustomJSONEncoder,
                    )

                    return ToolResponse(content=[TextBlock(type="text", text=ret_json)])
                else:
                    # 4. 如果是 DML (UPDATE, INSERT, DELETE) 且在非只读模式下
                    await conn.commit()
                    return ToolResponse(
                        content=[
                            TextBlock(
                                type="text", text=f"执行成功，影响 {result.rowcount} 行"
                            )
                        ]
                    )

        except ValueError as e:
            logging.error(f"SQL 安全拒绝: {e}")
            return ToolResponse(
                content=[TextBlock(type="text", text=f"错误: SQL 安全拒绝: {str(e)}")]
            )
        except Exception as e:
            logging.error(f"执行 SQL 失败: {e}\nSQL: {sql}")
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"错误: 数据库执行异常，请检查 SQL 语法或权限。\n信息: {str(e)}",
                    )
                ]
            )

    async def close(self) -> None:
        """关闭数据库引擎"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            logging.info("数据库引擎已关闭")
