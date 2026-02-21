import pytest
from openbot.botflow.evolution import CodeChange, GitManager, ApprovalSystem, EvolutionController


class TestCodeChange:
    """测试 CodeChange 类"""
    
    def test_code_change_creation(self):
        """测试创建 CodeChange"""
        change = CodeChange(
            file_path="test.py",
            old_content="old code",
            new_content="new code",
            description="Test change"
        )
        assert change.file_path == "test.py"
        assert change.old_content == "old code"
        assert change.new_content == "new code"
        assert change.description == "Test change"


class TestGitManager:
    """测试 GitManager 类"""
    
    def test_commit(self):
        """测试提交更改"""
        manager = GitManager()
        change = CodeChange(
            file_path="test.py",
            old_content="old code",
            new_content="new code",
            description="Test change"
        )
        commit_hash = manager.commit([change], "Test commit")
        assert isinstance(commit_hash, str)
        assert commit_hash == "dummy-commit-hash"
    
    def test_rollback(self):
        """测试回滚更改"""
        manager = GitManager()
        result = manager.rollback("dummy-commit-hash")
        assert result is True


class TestApprovalSystem:
    """测试 ApprovalSystem 类"""
    
    def test_request_approval(self):
        """测试请求审批"""
        system = ApprovalSystem()
        change = CodeChange(
            file_path="test.py",
            old_content="old code",
            new_content="new code",
            description="Test change"
        )
        result = system.request_approval([change])
        assert result is True


class TestEvolutionController:
    """测试 EvolutionController 类"""
    
    async def test_propose_change(self):
        """测试提议更改"""
        git_manager = GitManager()
        approval_system = ApprovalSystem()
        controller = EvolutionController(git_manager, approval_system)
        
        change = CodeChange(
            file_path="test.py",
            old_content="old code",
            new_content="new code",
            description="Test change"
        )
        
        result = await controller.propose_change(change)
        assert result is True
    
    async def test_apply_change(self):
        """测试应用更改"""
        git_manager = GitManager()
        approval_system = ApprovalSystem()
        controller = EvolutionController(git_manager, approval_system)
        
        # 创建临时测试文件
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('old code')
            temp_file = f.name
        
        try:
            change = CodeChange(
                file_path=temp_file,
                old_content='old code',
                new_content='new code',
                description='Test change'
            )
            
            result = await controller.apply_change(change)
            assert result is True
            
            # 验证文件内容是否已更改
            with open(temp_file, 'r') as f:
                content = f.read()
            assert content == 'new code'
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    async def test_rollback(self):
        """测试回滚更改"""
        git_manager = GitManager()
        approval_system = ApprovalSystem()
        controller = EvolutionController(git_manager, approval_system)
        
        result = await controller.rollback("dummy-commit-hash")
        assert result is True
