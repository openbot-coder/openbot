from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CodeChange:
    """代码修改"""

    file_path: str
    old_content: str
    new_content: str
    description: str


class GitManager:
    """Git 管理"""

    def commit(self, changes: List[CodeChange], message: str) -> str:
        """提交更改"""
        # TODO: 实现 Git 提交逻辑
        return "dummy-commit-hash"

    def rollback(self, commit_hash: str) -> bool:
        """回滚到指定提交"""
        # TODO: 实现 Git 回滚逻辑
        return True


class ApprovalSystem:
    """审批系统"""

    def request_approval(self, changes: List[CodeChange]) -> bool:
        """请求用户审批"""
        # TODO: 实现审批请求逻辑
        print("\n=== Code Change Approval ===")
        for change in changes:
            print(f"File: {change.file_path}")
            print(f"Description: {change.description}")
            print("\nOld content:")
            print(change.old_content)
            print("\nNew content:")
            print(change.new_content)
            print("\n" + "-" * 50 + "\n")
        return True  # 暂时默认批准


class EvolutionController:
    def __init__(self, git_manager: GitManager, approval_system: ApprovalSystem):
        self.git_manager = git_manager
        self.approval_system = approval_system

    async def propose_change(self, change: CodeChange) -> bool:
        """提议代码修改，等待用户审批"""
        return self.approval_system.request_approval([change])

    async def apply_change(self, change: CodeChange) -> bool:
        """应用已批准的修改"""
        # 写入文件
        try:
            with open(change.file_path, "w", encoding="utf-8") as f:
                f.write(change.new_content)
            # 提交到 Git
            commit_hash = self.git_manager.commit([change], change.description)
            print(f"Change applied and committed: {commit_hash}")
            return True
        except Exception as e:
            print(f"Error applying change: {e}")
            return False

    async def rollback(self, commit_hash: str) -> bool:
        """回滚到指定版本"""
        return self.git_manager.rollback(commit_hash)
