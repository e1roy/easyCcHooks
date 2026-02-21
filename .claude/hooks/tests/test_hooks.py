#!/usr/bin/env python3
"""
测试 Claude Code Hooks 框架

测试 example_hooks.py 中的示例 hook 实现。
使用前需要先将 example_hooks.py 复制到上级 hooks 目录:
  cp example_hooks.py ../
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
HOOKS_DIR = SCRIPT_DIR.parent
CLI = HOOKS_DIR / "easyCcHooks.py"


def test_hook_via_stdin(hook_name, input_file):
    """通过 stdin 测试 hook (模拟 Claude Code 调用方式)"""
    print(f"\n{'='*60}")
    print(f"测试: {hook_name} (输入: {input_file.name})")
    print(f"{'='*60}")

    try:
        with open(input_file) as f:
            input_data = f.read()

        result = subprocess.run(
            [sys.executable, str(CLI), "execute", hook_name],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            output = json.loads(result.stdout.strip())
            print(f"  输出: {json.dumps(output, indent=2, ensure_ascii=False)}")
            print(f"  ✓ 成功")
            return True, output
        else:
            print(f"  ✗ 失败 (退出码 {result.returncode})")
            if result.stderr:
                print(f"  错误: {result.stderr.strip()}")
            return False, None

    except json.JSONDecodeError as e:
        print(f"  ✗ JSON 解析失败: {e}")
        print(f"  stdout: {result.stdout}")
        return False, None
    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False, None


def test_hook_via_cli(hook_name, input_file):
    """通过 CLI test 命令测试 hook"""
    print(f"\n{'='*60}")
    print(f"CLI 测试: {hook_name} (输入: {input_file.name})")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            [sys.executable, str(CLI), "test", hook_name, "--input", str(input_file)],
            capture_output=True,
            text=True,
            timeout=10
        )

        print(f"  {result.stdout.strip()}")
        if result.returncode == 0:
            print(f"  ✓ 成功")
            return True
        else:
            print(f"  ✗ 失败 (退出码 {result.returncode})")
            if result.stderr:
                print(f"  错误: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False


def main():
    print("Claude Code Hooks 框架测试")
    print("=" * 60)

    # 检查 CLI 脚本
    if not CLI.exists():
        print(f"✗ 错误: 找不到 {CLI}")
        sys.exit(1)
    print(f"✓ 找到 CLI: {CLI}")

    # 检查示例 hook 是否在 hooks 目录下
    example_in_hooks = HOOKS_DIR / "example_hooks.py"
    if not example_in_hooks.exists():
        print(f"\n⚠️  示例 hook 不在 hooks 目录下,正在复制...")
        import shutil
        shutil.copy(SCRIPT_DIR / "example_hooks.py", example_in_hooks)
        print(f"✓ 已复制 example_hooks.py → {example_in_hooks}")
        cleanup_example = True
    else:
        cleanup_example = False

    # 检查 scan
    print(f"\n{'='*60}")
    print("扫描 hook...")
    print(f"{'='*60}")
    scan_result = subprocess.run(
        [sys.executable, str(CLI), "scan"],
        capture_output=True,
        text=True,
        timeout=10
    )
    print(f"  {scan_result.stdout.strip()}")

    # 测试文件
    test_dangerous = SCRIPT_DIR / "test_input_dangerous.json"
    test_safe = SCRIPT_DIR / "test_input_safe.json"
    test_session = SCRIPT_DIR / "test_input_session.json"

    passed = 0
    failed = 0
    tests = []

    # 1. ValidateBashCommand - 危险命令 (应该 deny)
    ok, output = test_hook_via_stdin("ValidateBashCommand", test_dangerous)
    if ok and output:
        hook_output = output.get("hookSpecificOutput", {})
        if hook_output.get("permissionDecision") == "deny":
            print(f"  ✓ 验证: 危险命令被正确拒绝")
            passed += 1
        else:
            print(f"  ✗ 验证失败: 期望 deny, 实际 {hook_output.get('permissionDecision')}")
            failed += 1
    else:
        failed += 1

    # 2. ValidateBashCommand - 安全命令 (应该 allow)
    ok, output = test_hook_via_stdin("ValidateBashCommand", test_safe)
    if ok and output:
        hook_output = output.get("hookSpecificOutput", {})
        if hook_output.get("permissionDecision") == "allow":
            print(f"  ✓ 验证: 安全命令被正确允许")
            passed += 1
        else:
            print(f"  ✗ 验证失败: 期望 allow, 实际 {hook_output.get('permissionDecision')}")
            failed += 1
    else:
        failed += 1

    # 3. InjectContext - 会话启动
    ok, output = test_hook_via_stdin("InjectContext", test_session)
    if ok and output:
        hook_output = output.get("hookSpecificOutput", {})
        if hook_output.get("additionalContext"):
            print(f"  ✓ 验证: 上下文已注入")
            passed += 1
        else:
            print(f"  ✗ 验证失败: 没有注入上下文")
            failed += 1
    else:
        failed += 1

    # 4. CLI test 命令
    if test_hook_via_cli("ValidateBashCommand", test_dangerous):
        passed += 1
    else:
        failed += 1

    # 清理复制的文件
    if cleanup_example and example_in_hooks.exists():
        example_in_hooks.unlink()
        print(f"\n✓ 已清理临时文件: {example_in_hooks}")

    # 汇总结果
    print(f"\n{'='*60}")
    print(f"测试结果")
    print(f"{'='*60}")
    print(f"✓ 通过: {passed}/{passed + failed}")
    print(f"✗ 失败: {failed}/{passed + failed}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
