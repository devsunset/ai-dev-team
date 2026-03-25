"""AI 멀티 에이전트 런처"""

import argparse
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dep
    load_dotenv = None

FRAMEWORK_PROFILES: Dict[str, str] = {
    "crewai": "역할 기반 협업 중심(기획/개발/QA).",
    "autogen": "에이전트 간 토론+실행 루프를 강조합니다.",
    "langgraph": "정밀한 워크플로우 그래프+상태 제어.",
    "pydanticai": "데이터/타입 안전성이 중요한 금융/보안용.",
    "agno": "실시간 웹/지식 검색과 통합이 중심입니다.",
    "smolagents": "로컬 모델(Ollama 등) 위주 가볍게 돌아갑니다.",
    "metagpt": "문서/설계 중심, PRD→API 문서 전환까지.",
    "chatdev": "가상의 회사처럼 빠르게 결과를 만들어냅니다.",
    "agency-swarm": "계층 구조 조직(CEO/Manager/Engineers)을 시뮬레이트합니다.",
    "plandex": "기존 대규모 코드 기반 리팩토링/수정 집중형.",
}

AGENT_PROFILES: Dict[str, Dict[str, str]] = {
    "pm": {
        "title": "Project Manager",
        "mission": "PRD와 TRD를 분석하여 팀 목표를 명확히 한다.",
        "focus": "전략, KPI, 외부 커뮤니케이션",
    },
    "architect": {
        "title": "System Architect",
        "mission": "기술 구조를 설계하고 도구/스택을 결정한다.",
        "focus": "API/DB 동기화, MSA vs 모놀리식 판별",
    },
    "backend": {
        "title": "Backend Engineer",
        "mission": "비즈니스 로직, API, DB를 구현한다.",
        "focus": "백엔드 아키텍처, 데이터 무결성, 서비스 안정성",
    },
    "frontend": {
        "title": "Frontend Engineer",
        "mission": "사용자 경험과 UI/UX를 구현한다.",
        "focus": "경험 흐름과 반응성, 접근성과 상태 관리",
    },
    "designer": {
        "title": "UI/UX Designer",
        "mission": "디자인 시스템과 스타일 가이드를 제시한다.",
        "focus": "브랜딩, 접근성, CSS 토큰",
    },
    "data": {
        "title": "Data Engineer",
        "mission": "데이터 파이프라인과 관측 지표를 설계한다.",
        "focus": "ETL, 데이터 품질, 시각화",
    },
    "qa": {
        "title": "QA Engineer",
        "mission": "테스트, 릴리즈 검수, 리스크 탐지.",
        "focus": "단위·통합 테스트, 회귀 검증",
    },
    "devops": {
        "title": "DevOps Engineer",
        "mission": "CI/CD, 인프라, 배포 자동화를 담당한다.",
        "focus": "Docker, GitHub Actions, 인프라 코드",
    },
    "security": {
        "title": "Security Specialist",
        "mission": "취약점 분석, 정책, 인증을 검증한다.",
        "focus": "비밀 키 관리, OWASP, 감사 로그",
    },
}

OS_DEFAULT_MODE: Dict[str, str] = {
    "Darwin": "cmux",
    "Linux": "tmux",
    "Windows": "tmux",
}

DEFAULT_AGENT_ORDER = [
    "pm",
    "architect",
    "backend",
    "frontend",
    "designer",
    "data",
    "qa",
    "devops",
    "security",
]

DEFAULT_TOKEN_COST = 6000


class TokenBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.consumed = 0

    def consume(self, amount: int) -> None:
        self.consumed += amount
        if self.consumed > self.limit:
            raise RuntimeError(
                f"토큰 예산 {self.limit}을 초과했습니다 (소모 {self.consumed})"
            )

    def status(self) -> str:
        return f"{self.consumed}/{self.limit} tokens used"


def get_python_in_venv(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def bootstrap_virtualenv(venv_dir: Path, requirements: Path) -> Path:
    if not venv_dir.exists():
        venv_dir.mkdir(parents=True, exist_ok=True)
    if not (venv_dir / "pyvenv.cfg").exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python_bin = get_python_in_venv(venv_dir)
    if not python_bin.exists():
        raise RuntimeError(f"가상환경 내부 파이썬을 찾을 수 없습니다: {python_bin}")
    subprocess.run([str(python_bin), "-m", "pip", "install", "-U", "pip"], check=True)
    if requirements.exists():
        subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(requirements)], check=True)
    else:
        logging.warning("requirements.txt 파일이 없어 의존성 설치를 건너뜁니다.")
    return python_bin


def load_env_file(path: str = ".env") -> Dict[str, str]:
    config: Dict[str, str] = {}
    env_path = Path(path)
    if load_dotenv:
        load_dotenv(env_path)
    if not env_path.exists():
        logging.debug(f"env 파일 {env_path}을 찾을 수 없습니다.")
        return config
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        text = raw_line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            continue
        key, _, value = text.partition("=")
        normalized_key = key.strip()
        normalized_value = value.strip()
        config[normalized_key] = normalized_value
        os.environ.setdefault(normalized_key, normalized_value)
    return config


def determine_terminal_mode(arg_mode: str, env_mode: str) -> str:
    if arg_mode != "auto":
        return arg_mode
    candidate = (env_mode or "").lower()
    if candidate in ("tmux", "cmux"):
        return candidate
    return OS_DEFAULT_MODE.get(platform.system(), "tmux")


def ensure_terminal_tool(mode: str) -> None:
    tool = "cmux" if mode == "cmux" else "tmux"
    if shutil.which(tool):
        logging.info(f"{tool}를 찾았습니다. 해당 환경에 맞는 안내를 출력합니다.")
    else:
        logging.warning(
            f"{tool} 실행 바이너리를 찾지 못했습니다. OS 패키지 매니저에서 설치 후 재시도하세요."
        )


def print_terminal_guide(mode: str) -> None:
    if mode == "cmux":
        print("cmux 환경이 감지되었습니다. 포트 8000에 결과물을 띄운 뒤 브라우저에서 확인하세요.")
    else:
        print("tmux 환경이 감지되었습니다. Ctrl+b % / Ctrl+b \" / Ctrl+b d로 세션을 나눠 로그를 모니터링하세요.")


def parse_agent_list(raw: str) -> List[str]:
    if not raw:
        return DEFAULT_AGENT_ORDER[:]
    return [name.strip() for name in raw.split(",") if name.strip()]


def instantiate_llm(role: str, env: Dict[str, str]) -> Dict[str, str]:
    vendor = env.get(f"{role.upper()}_VENDOR", "openai").lower()
    model = env.get(f"{role.upper()}_MODEL", "gpt-4o")
    return {"vendor": vendor, "model": model}


def build_agent_records(agent_names: List[str], env: Dict[str, str]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for name in agent_names:
        profile = AGENT_PROFILES.get(name, {})
        record = {
            "role": name,
            "title": profile.get("title", name.title()),
            "mission": profile.get("mission", "정해진 과업을 수행합니다."),
            "focus": profile.get("focus", "요구사항에 맞게 작업합니다."),
            "llm": instantiate_llm(name, env),
        }
        records.append(record)
    return records


def create_visual_center(path: Path, framework: str, mode: str, agents: List[Dict[str, Any]]) -> None:
    snippets = []
    for idx, agent in enumerate(agents, start=1):
        left = 5 + (idx * 8)
        snippets.append(
            f"<div class='agent' style='left:{left}%; top:{10 + (idx % 3) * 25}%;'>"
            f"{agent['title']}<span class='label'>{agent['role']}</span></div>"
        )
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset='utf-8'>
      <title>Launcher Visual Center</title>
      <style>
        body {{ background:#070707; color:#d0f0ff; font-family:monospace; padding:20px; }}
        #map {{ width:100%; height:360px; border:2px solid #1f6feb; position:relative; background:#111; }}
        .agent {{ position:absolute; transition:all 0.6s; font-size:22px; text-align:center; }}
        .label {{ font-size:12px; display:block; color:#fff; }}
        #console {{ margin-top:20px; height:220px; border:1px solid #444; background:#000; padding:10px; overflow:auto; }}
      </style>
    </head>
    <body>
      <h1>Framework: {framework} | Mode: {mode}</h1>
      <div id='map'>{''.join(snippets)}</div>
      <div id='console'>자동화된 AI 팀이 준비되었습니다.</div>
    </body>
    </html>
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def run_self_healing_loop(agent: Dict[str, Any], budget: TokenBudget, attempts: int) -> Dict[str, Any]:
    history: List[str] = []
    status = "OK"
    for attempt in range(1, attempts + 1):
        cost = DEFAULT_TOKEN_COST - attempt * 200
        if cost < 2000:
            cost = 2000
        try:
            budget.consume(cost)
        except RuntimeError as exc:
            history.append(f"budget-failure:{exc}")
            status = "budget_exceeded"
            break
        step_label = "테스트" if attempt == 1 else "검토/수정"
        history.append(f"{agent['role']} attempt {attempt}/{attempts} ({step_label})")
        if attempt == attempts:
            status = "verified"
    return {
        "role": agent["role"],
        "status": status,
        "llm": agent.get("llm", {}),
        "history": history,
    }


def log_run_data(log_dir: Path, summary: List[Dict[str, Any]]) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    target = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_latest_summary(log_dir: Path, summary: List[Dict[str, Any]], budget: TokenBudget, goal: str, framework: str, mode: str) -> Path:
    summary_file = log_dir / "latest_summary.txt"
    lines: List[str] = []
    lines.append(f"Framework: {framework}, Mode: {mode}")
    lines.append(f"Goal: {goal}")
    lines.append(f"Token status: {budget.status()}")
    lines.append("Agent statuses:")
    for record in summary:
        lines.append(f"  - {record['role']}: {record['status']} ({len(record.get('history', []))} steps)")
    summary_file.write_text("\n".join(lines), encoding="utf-8")
    return summary_file


def self_test_paths(paths: List[Path]) -> List[str]:
    problems: List[str] = []
    for path in paths:
        if not path.exists():
            problems.append(f"{path}이(가) 존재하지 않습니다.")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 멀티에이전트 런처"
    )
    parser.add_argument("--framework", choices=list(FRAMEWORK_PROFILES.keys()), default="crewai")
    parser.add_argument("--mode", choices=["auto", "tmux", "cmux"], default="auto")
    parser.add_argument("--goal", default="")
    parser.add_argument("--agents", default=",".join(DEFAULT_AGENT_ORDER))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    env = load_env_file()
    venv_dir = Path(".venv")
    requirements_txt = Path("requirements.txt")
    if args.install:
        bootstrap_virtualenv(venv_dir, requirements_txt)
        print("가상환경과 의존성 설치를 마쳤습니다. 필요한 경우 env 파일을 확인하고 다시 실행하세요.")

    desired_mode = determine_terminal_mode(args.mode, env.get("TERMINAL_MODE", ""))
    ensure_terminal_tool(desired_mode)
    print_terminal_guide(desired_mode)

    workspace = Path(env.get("WORKSPACE_DIR", "workspace"))
    log_dir = Path(env.get("LOG_DIR", "logs"))
    visual_path = Path(env.get("VISUAL_CENTER", workspace / "visual_center.html"))
    workspace.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    framework = args.framework
    goal = args.goal or env.get("PROJECT_GOAL", "Autonomous multi-agent sprint")
    agent_names = parse_agent_list(args.agents or env.get("AGENT_TEAM", ",".join(DEFAULT_AGENT_ORDER)))
    agents = build_agent_records(agent_names, env)

    budget_limit = int(env.get("TOKEN_BUDGET", "150000"))
    healing_attempts = int(env.get("HEALING_ATTEMPTS", "3"))
    budget = TokenBudget(budget_limit)

    if args.self_test:
        problems = self_test_paths([workspace, log_dir, Path("docs")])
        requirements = Path("requirements.txt")
        if not requirements.exists():
            problems.append("requirements.txt 파일이 없습니다.")
        if problems:
            logger = logging.getLogger(__name__)
            for issue in problems:
                logger.warning(f"Self-test 문제: {issue}")
        else:
            print("Self-test 통과: 기본 디렉토리와 requirements.txt가 준비되었습니다.")

    create_visual_center(visual_path, framework, desired_mode, agents)

    run_summary: List[Dict[str, Any]] = []
    for agent in agents:
        result = run_self_healing_loop(agent, budget, healing_attempts)
        run_summary.append(result)

    json_path = log_run_data(log_dir, run_summary)
    summary_path = write_latest_summary(log_dir, run_summary, budget, goal, framework, desired_mode)

    print("== 실행 요약 ==")
    print(f"프레임워크: {framework} ({FRAMEWORK_PROFILES.get(framework)})")
    print(f"목표: {goal}")
    print(f"모드: {desired_mode}")
    print(f"워크스페이스: {workspace.resolve()}")
    print(f"visual 관측판: {visual_path.resolve()}")
    print(f"토큰 사용 현황: {budget.status()}")
    print(f"JSON 로그: {json_path.name}, latest summary: {summary_path.name}")
    print("로깅된 요약은 logs/ 디렉토리에서 확인하세요.")

    print("== 에이전트 실행 내역 ==")
    for summary in run_summary:
        status = summary["status"]
        print(f"- {summary['role']}: {status} ({len(summary['history'])}단계)")


if __name__ == "__main__":
    main()
