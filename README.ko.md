# ctxforge

AI CLI를 위한 간단한 컨텍스트 관리 도구입니다.

프로필을 정의하고 핵심 파일을 선택한 뒤, 프로젝트 컨텍스트와 함께 AI CLI를 실행합니다.

## 설치

```bash
pip install ctxforge
```

Python 3.11 이상이 필요하며, 최소 1개의 AI CLI(예: [Claude Code](https://docs.anthropic.com/en/docs/claude-code))가 설치되어 있어야 합니다.

## 빠른 시작 (2단계)

```bash
cd your-project/

# 1) 초기화
ctxforge init

# 2) 실행
ctxforge run
```

`ctxforge init`은 프로젝트 설정과 첫 번째 프로필을 생성합니다.

`ctxforge run`은 해당 프로필을 불러와, 선택한 컨텍스트로 대화형 AI CLI 세션을 시작합니다.

## 자주 쓰는 명령어

| 명령어 | 설명 |
|--------|------|
| `ctxforge init [PATH]` | 프로젝트의 ctxforge 설정 초기화 |
| `ctxforge run [PROFILE]` | 지정한 프로필로 AI CLI 세션 시작 |
| `ctxforge profile create NAME` | 새 프로필 생성 |
| `ctxforge profile list` | 모든 프로필 목록 보기 |
| `ctxforge profile show NAME` | 프로필 상세 보기 |
| `ctxforge clean [PATH]` | 모든 ctxforge 설정 제거 |

## 최소 예시

```bash
ctxforge profile create reviewer --desc "Code review" --prompt "You are a code reviewer..."
ctxforge run reviewer
```

## 내장 슬래시 명령어 (Claude Code 전용)

Claude Code를 활성 CLI로 사용할 때, ctxforge는 `/project:ctx-*` 슬래시 명령어를 생성합니다:

| 명령어 | 설명 |
|--------|------|
| `/project:ctx-profile` | 현재 프로필 설정 보기 |
| `/project:ctx-files` | key files 목록과 크기 정보 |
| `/project:ctx-update` | AI가 key files 업데이트 제안 |
| `/project:ctx-compress` | AI가 장황한 key files 압축 |

이 명령어들은 다른 CLI(예: Codex)에서는 사용할 수 없습니다.

## 참고

ctxforge의 프로젝트/프로필 설정 파일은 `.ctxforge/` 아래에 저장됩니다.
필요하면 사용자가 직접 수정할 수 있습니다.
수정 후에는 `ctxforge run`을 다시 실행해야 변경된 컨텍스트가 적용됩니다.

## 라이선스
MIT
