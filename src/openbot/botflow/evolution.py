from dataclasses import dataclass
from typing import List, Optional
import subprocess
import os


@dataclass
class CodeChange:
    """代码修改"""

    file_path: str
    old_content: str
    new_content: str
    description: str


class GitManager:
    """Git 管理"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def _run_git_command(self, args: List[str]) -> str:
        """运行 Git 命令"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {e}")
            print(f"Error output: {e.stderr}")
            return ""

    def commit(self, changes: List[CodeChange], message: str) -> str:
        """提交更改"""
        try:
            # 添加修改的文件
            for change in changes:
                self._run_git_command(["add", change.file_path])
            
            # 提交更改
            commit_hash = self._run_git_command(["commit", "-m", message])
            
            # 提取提交哈希
            if commit_hash:
                # 尝试从输出中提取哈希
                import re
                match = re.search(r'\[.*?([0-9a-f]{40})\]', commit_hash)
                if match:
                    return match.group(1)
                return commit_hash
            return ""
        except Exception as e:
            print(f"Error committing changes: {e}")
            return ""

    def rollback(self, commit_hash: str) -> bool:
        """回滚到指定提交"""
        try:
            # 执行硬重置
            self._run_git_command(["reset", "--hard", commit_hash])
            return True
        except Exception as e:
            print(f"Error rolling back: {e}")
            return False

    def get_current_commit(self) -> str:
        """获取当前提交哈希"""
        return self._run_git_command(["rev-parse", "HEAD"])

    def status(self) -> str:
        """获取 Git 状态"""
        return self._run_git_command(["status"])


class ApprovalSystem:
    """审批系统"""

    def request_approval(self, changes: List[CodeChange]) -> bool:
        """请求用户审批"""
        print("\n=== Code Change Approval ===")
        for change in changes:
            print(f"File: {change.file_path}")
            print(f"Description: {change.description}")
            print("\nOld content:")
            print(change.old_content)
            print("\nNew content:")
            print(change.new_content)
            print("\n" + "-" * 50 + "\n")
        
        # 询问用户是否批准
        while True:
            response = input("Do you approve these changes? (y/n): ").strip().lower()
            if response == "y":
                return True
            elif response == "n":
                return False
            else:
                print("Please enter 'y' or 'n'.")


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
            if commit_hash:
                print(f"Change applied and committed: {commit_hash}")
                return True
            else:
                print("Failed to commit changes")
                return False
        except Exception as e:
            print(f"Error applying change: {e}")
            return False

    async def rollback(self, commit_hash: str) -> bool:
        """回滚到指定版本"""
        return self.git_manager.rollback(commit_hash)

    async def propose_changes(self, changes: List[CodeChange]) -> bool:
        """提议多个代码修改，等待用户审批"""
        return self.approval_system.request_approval(changes)

    async def apply_changes(self, changes: List[CodeChange], message: str) -> bool:
        """应用多个已批准的修改"""
        try:
            # 写入文件
            for change in changes:
                with open(change.file_path, "w", encoding="utf-8") as f:
                    f.write(change.new_content)
            # 提交到 Git
            commit_hash = self.git_manager.commit(changes, message)
            if commit_hash:
                print(f"Changes applied and committed: {commit_hash}")
                return True
            else:
                print("Failed to commit changes")
                return False
        except Exception as e:
            print(f"Error applying changes: {e}")
            return False
