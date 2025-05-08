# CodeSnap

CodeSnap is an AI-powered code snapshot tool that helps developers manage code changes in a controlled manner.

## Installation

```bash
pip install .
```

## Usage

```
CS - CodeSnap AI-powered code snapshot tool

Usage: cs [COMMAND] [OPTIONS]

Commands:
  init               Initialize a new repository with CodeSnap
  start              Create a new task branch
  commit             Commit changes to the current task branch
  apply              Apply all changes to the main branch without committing
  merge              Apply all changes to the main branch
  abort              Abandon all changes in the current task
  list               List all task branches
  log                View commits in the current task
  diff               Show differences between task branch and main branch
  prune              Clean up old task branches

Examples:
  $ cs start feature-login
  $ cs commit "Fix login button style"
  $ cs apply
```

## Features

- **Task-based development**: Create isolated task branches for each feature or bug fix
- **Simple workflow**: Easy to use commands for common Git operations
- **Clean history**: Option to squash commits when merging
- **Automatic cleanup**: Prune old task branches to keep your repository clean

## License

MIT

## 设计
当创建新文件时，如果AI认为需要将该文件排除，则由AI将其添加至.gitignore，否则commit时ai会将其自动将其提交至commit中