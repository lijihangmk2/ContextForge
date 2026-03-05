# Git

- 推送时使用 noqi_git SSH key：
  ```
  GIT_SSH_COMMAND="ssh -i ~/.ssh/noqi_git -o IdentitiesOnly=yes" git push origin main
  ```
- commit 不要署名 Claude

# PyPI

- Token 文件：`docs/token`
- 上传命令：
  ```
  python3 -m build && python3 -m twine upload dist/ctxforge-<version>* -u __token__ -p "$(cat docs/token)"
  ```

# Pitfalls

- **终端标题由 `setproctitle` 决定，不是 OSC 转义序列**：在 WSL2 + Windows Terminal 环境下，终端标签标题取自进程名（`setproctitle`），而非 `\033]0;...\007` 转义序列。修改终端标题时必须同时调用 `setproctitle()`。
