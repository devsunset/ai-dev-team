# AI Multi-Agent Hyper-Launcher

## 개요
이 저장소는 tmux와 cmux 터미널 위에서 작동하는 AI 멀티 에이전트 개발 팀을 한 번에 부팅하고 관리하는 파이썬 실행기입니다. OS를 감지하여 macOS에서는 cmux를, Windows/Linux에서는 tmux를 기본으로 선택하며, 인자로 전달할 수 있는 프레임워크(crewAI, AutoGen, Langgraph 등)와 작전 목표에 맞게 에이전트 팀을 조합합니다.

## 준비
1. `python --version`이 3.11 이상인지 확인합니다.
2. `python -m venv .venv`로 가상환경을 만들고 활성화하거나 `python3 main.py --install`을 통해 자동 생성합니다.
3. `pip install -r requirements.txt`로 의존성을 설치합니다. (자동 설치 시점도 `--install`에서 처리합니다.)
4. `.env`를 열어 API 키, 서버 목표, 에이전트 구성, 토큰 예산 등을 직접 주석을 읽으며 입력합니다.

## .env 파일 설명
- `.env`는 사람이 읽을 수 있도록 섹션별로 최대한 많은 설명을 붙였습니다.
- 기본값은 `FRAMEWORK=crewai`, `PROJECT_GOAL=풀스택 AI 개발팀이 PRD/TRD 기반으로 결과물을 자동 작성/검증하는 워크플로우`, `TOKEN_BUDGET=200000`, `HEALING_ATTEMPTS=4`로 설정되어 있어, 일반적인 멀티에이전트 개발 프로젝트의 성능과 안정성을 겨냥합니다.
- 모드 관련: `TERMINAL_MODE`를 비워두면 프로그램이 `platform.system()` 값을 읽어 macOS에서는 `cmux`, 나머지에서는 `tmux`를 선택합니다. 필요한 경우 `tmux`나 `cmux`를 명시적으로 오버라이드할 수도 있습니다.
- 경로 관련: `WORKSPACE_DIR`, `LOG_DIR`, `VISUAL_CENTER`는 실행 결과물, 로그, HTML 관측판 위치를 설정하는 핵심 항목입니다.
- 프레임워크: `FRAMEWORK`에는 `crewai`, `autogen`, `langgraph`, `pydanticai`, `agno`, `smolagents`, `metagpt`, `chatdev`, `agency-swarm`, `plandex`를 넣어 간단히 전환할 수 있으며, CLI `--framework`와도 연동됩니다.
-   * `crewai`: 역할 기반 협업 중심(기획→개발→QA)을 시뮬레이션합니다.
-   * `autogen`: 에이전트 간 토론과 자동 실행 루프를 활용합니다.
-   * `langgraph`: 정밀한 워크플로우 그래프와 상태 제어가 핵심입니다.
-   * `pydanticai`: 데이터/타입 안정성이 중요한 금융·보안 업무에 적합합니다.
-   * `agno`: 실시간 웹 검색, 외부 지식 통합이 중심인 정보형 프로젝트.
-   * `smolagents`: Ollama 등 로컬 모델 중심으로 가볍게 동작합니다.
-   * `metagpt`: PRD/TRD 기반 문서 및 설계 생성에 특화되어 있습니다.
-   * `chatdev`: 가상의 스타트업처럼 빠르게 결과를 투입하는 스피드 집중.
-   * `agency-swarm`: 계층 조직(CEO → 관리자 → 개발자) 구조를 시뮬레이트합니다.
-   * `plandex`: 기존 대규모 코드베이스 리팩토링/수정 집중형 워크플로우.
- 가상환경: `.venv`는 현재 실행 디렉터리에 자동으로 생성되며, `main.py --install`이 이를 만들고 `pip install -r requirements.txt`를 수행합니다.
- API 관련: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`에 각각 키를 채우면 해당 벤더를 로우팅할 수 있습니다.
- 에이전트 지능: `PM_VENDOR`, `DEV_VENDOR`, `QA_VENDOR` 아래에 `*_MODEL`도 함께 적어두면 역할별로 다른 LLM을 할당하게 됩니다.
- 운영 옵션: `TOKEN_BUDGET`은 전체 작업에서 소모할 토큰 한도, `HEALING_ATTEMPTS`는 self-healing 루프 반복 횟수를 제어합니다.

## CLI 인자
- `--framework`: 실행할 프레임워크를 선택합니다 (default: `crewai`). 지원 프레임워크는 `crewai`, `autogen`, `langgraph`, `pydanticai`, `agno`, `smolagents`, `metagpt`, `chatdev`, `agency-swarm`, `plandex`입니다.
- `--mode`: `auto`, `tmux`, `cmux` 중 하나를 선택. `auto`면 OS 감지 로직이 작동합니다.
- `--goal`: AI 팀이 달성할 메인 목표. `.env`에 적힌 `PROJECT_GOAL`을 기본값으로 사용합니다.
- `--agents`: 쉼표로 나열한 전문 에이전트(예: `pm,backend,frontend,qa,devops,security,designer`)를 순서대로 가동합니다.
- `--self-test`: 실제 작업 전에 주요 디렉토리와 파일을 확인하는 간단한 자체 점검을 실행합니다.
- `--install`: 실행 디렉터리의 `.venv`를 만들고 `pip install -r requirements.txt`을 실행한 뒤 설정을 마무리합니다.

## 터미널 모드 가이드
- macOS: `cmux`가 지원하는 내장 브라우저를 통해 결과물을 확인할 수 있으므로 기본 모드입니다. `cmux`가 설치되어 있지 않다면 `brew install cmux`를 먼저 실행하십시오.
- Windows/Linux: `tmux`를 사용합니다 (`sudo apt install tmux` 또는 WSL2 + `sudo apt install tmux`). GUI 없이 로그 중심으로 모니터링하며, 필요 시 `cmux`를 사용하고 싶다면 macOS에서 실행하세요.
- 실행 시 모드가 `tmux`이면 `Ctrl+b %`와 `Ctrl+b "`로 분할, `Ctrl+b d`로 배경 실행하는 안내가 출력됩니다.

## 에이전트 팀 구성
모든 에이전트는 역할(기획/설계, 백엔드, 프론트, QA, DevOps, 보안, 디자인, 데이터)과 persona, 핵심 책임을 가지고 있습니다. 예:
- `pm`: PRD/TRD를 읽고 전체 전략을 정리합니다.
- `backend`: 비즈니스 로직 구현, API/DB 설계를 담당합니다.
- `frontend`: UI/UX 설계 및 사용자 흐름을 조율합니다.
- `qa`: 테스트 시나리오, 버그 리포트, 릴리즈 검수를 진행합니다.
- `devops`/`security`: 인프라, 배포, 보안 정책을 강화합니다.

각 에이전트는 `TokenBudget`이 제공한 토큰/비용 제한을 참고해 `HEALING_ATTEMPTS` 횟수만큼 self-healing 루프를 돌면서 코드·문서를 다듬고, `logs/` 아래에 타임스탬프가 붙은 로그를 남깁니다.

## 실행 흐름 및 검증
1. 터미널에 `python main.py --framework langgraph --mode auto --goal "실시간 데이터 통합 플랫폼 구축"`처럼 명령을 입력합니다.
2. 스크립트가 `.env`와 OS를 기반으로 터미널 모드를 결정, 필요한 디렉토리를 만들고 `workspace/visual_center.html`을 생성합니다.
3. 각 에이전트는 인자와 env를 조합하여 persona, LLM 매핑을 확인하고 self-healing 검사(테스트 → 실패 → 수정 → 재검토)를 실행합니다.
4. 토큰 예산이 초과되면 안전하게 종료하고 로그에 자세한 원인을 기록합니다.
5. `--self-test`를 함께 지정하면 실행 전에 `workspace/`, `logs/`, `docs/`를 미리 점검하고 `requirements.txt`가 존재하는지 확인합니다.
6. 실행 완료 후 `logs/run_*.json`과 `logs/latest_summary.txt`를 열어 에이전트별 상태, 토큰 소비와 목표를 다시 확인하세요.

## Visual center
`workspace/visual_center.html`에는 현재 실행된 에이전트가 미리 정의된 좌표와 상태 메시지를 갱신한 기본 HTML 템플릿이 생성됩니다. cmux에서 브라우저 창을 연 뒤 경로를 붙여 넣으면 실시간 관측이 가능합니다.

## 다음 단계 제안
- `requirements.txt`를 사용해 의존성을 설치한 뒤 `main.py --self-test`로 환경 점검을 먼저 실행해 보십시오.
- `docs/`에 PRD/TRD를 추가하고 `--goal`을 구체화하면 에이전트가 더 명확한 지침을 받습니다.
- cmux를 활용하는 macOS에서는 하나의 창에 브라우저와 로그를 동시에 띄워 결과물을 확인하세요.
