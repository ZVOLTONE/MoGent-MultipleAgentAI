#!/usr/bin/env python3
"""AISector-MoGent - Terminal CLI (PRD 18).

Usage:
    python main.py            # normal mode
    python main.py --debug    # show full orchestration trace

Commands inside the REPL:
    /agents                      list all agents (base + derived)
    /agents show <id>            show an agent spec
    /agents lineage <id>         show a derived agent's lineage
    exit | quit                  leave
"""
from __future__ import annotations

import json
import sys

from config import config, ensure_dirs
from backend.agent_factory.registry import AgentRegistry, IntegrityError
from backend.agent_factory import lineage as lineage_mod
from backend.orchestrator.orchestrator import Orchestrator
from backend.llm.ollama import OllamaClient

LINE = "=" * 50


def banner(registry: AgentRegistry):
    base_n = len(registry.base_agents())
    der_n = len(registry.derived_agents())
    print(LINE)
    print(" AISector-MoGent")
    print(" Investment Multi-Agent System")
    print(LINE)
    print("\nModel:")
    print(f"Orchestrator : {config.ORCHESTRATOR_MODEL}")
    print(f"Specialist   : {config.SPECIALIST_MODEL}")
    print(f"Agents       : {base_n} base \u00b7 {der_n} derived")
    print("\nPerintah: /agents \u00b7 /agents show <id> \u00b7 /agents lineage <id> \u00b7 exit\n")


def cmd_agents(registry: AgentRegistry, args: list[str]):
    if not args:
        print("\nDAFTAR AGENT")
        print("-" * 50)
        for s in registry.base_agents():
            print(f"  [base]    {s['agent_id']}@{s['version']}  - {s.get('display_name','')}")
        derived = registry.derived_agents()
        if derived:
            for s in derived:
                print(f"  [derived] {s['agent_id']}@{s['version']}  - {s.get('display_name','')}")
        else:
            print("  (belum ada agent turunan)")
        print()
        return

    sub = args[0]
    if sub == "show" and len(args) >= 2:
        spec = registry.get(args[1])
        if not spec:
            print(f"Agent '{args[1]}' tidak ditemukan.\n")
            return
        print(json.dumps(spec, ensure_ascii=False, indent=2))
        print()
    elif sub == "lineage" and len(args) >= 2:
        spec = registry.get(args[1])
        if not spec:
            print(f"Agent '{args[1]}' tidak ditemukan.\n")
            return
        if spec.get("kind") != "derived":
            print(f"{args[1]} adalah agent base (tidak memiliki lineage turunan).\n")
            return
        print("\n[LINEAGE]")
        print(lineage_mod.render(spec))
        print()
    else:
        print("Penggunaan: /agents | /agents show <id> | /agents lineage <id>\n")


def print_result(result: dict, debug: bool):
    fac = result.get("agent_factory", {})
    print("\n[ORCHESTRATOR]")
    print(f"Intent   : {', '.join(result.get('intent', []))}")
    print(f"Persona  : {', '.join(result.get('persona', [])) or '(tidak terdeteksi)'}")
    print(f"Agents   : {', '.join(result.get('agents_used', [])) or '(tidak ada)'}")

    if fac.get("invoked"):
        print("\n[AGENT FACTORY]")
        print(f"Operasi  : {fac.get('operation', '').upper()}")
        print(f"Induk    : {', '.join(fac.get('parents', [])) or '-'}")
        if fac.get("reused"):
            print("Status   : REUSE (tidak membuat agent duplikat)")
        elif fac.get("failed"):
            print(f"Status   : GAGAL -> {fac.get('errors')}")
        else:
            v = fac.get("validations", {})
            checks = "  ".join(f"{'\u2713' if ok else '\u2717'} {k}" for k, ok in v.items())
            print(f"Validasi : {checks}")
            print(f"Hasil    : {fac.get('new_agent_id')}@{fac.get('version')} (baru)")
            print("Catatan  : agent induk tidak diubah")

    # tool status
    if result.get("tool_calls"):
        print("\n[TOOLS]")
        for tc in result["tool_calls"]:
            print(f"  {tc['glyph']} {tc['tool']}  {tc.get('args', '')}")

    if result.get("contradictions"):
        print("\n[KONTRADIKSI]")
        for c in result["contradictions"]:
            print(f"  - {c}")

    print("\n[JAWABAN]")
    print(result.get("answer", ""))

    if result.get("limitations"):
        print("\n[KETERBATASAN]")
        for l in result["limitations"]:
            print(f"  - {l}")

    if debug:
        print("\n[DEBUG TRACE]")
        print(json.dumps(result.get("_trace", {}), ensure_ascii=False, indent=1, default=str))
    print()


def main():
    debug = "--debug" in sys.argv
    ensure_dirs()

    try:
        registry = AgentRegistry()
        registry.verify_integrity()
    except IntegrityError as e:
        print("FATAL:", e)
        sys.exit(1)

    if not OllamaClient().available():
        print(f"PERINGATAN: Ollama tidak terjangkau di {config.OLLAMA_BASE_URL}. "
              f"Jalankan 'ollama serve' terlebih dahulu.\n")

    banner(registry)
    orc = Orchestrator(debug=debug)

    while True:
        try:
            line = input("User > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSampai jumpa.")
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            print("Sampai jumpa.")
            break
        if line.startswith("/agents"):
            cmd_agents(orc.registry, line.split()[1:])
            continue
        if line.startswith("/"):
            print("Perintah tidak dikenal. Coba /agents.\n")
            continue

        print("\nOrchestrator > memproses...")
        try:
            result = orc.handle(line)
            print_result(result, debug)
        except Exception as e:  # keep the REPL alive on any error
            print(f"[ERROR] {type(e).__name__}: {e}\n")


if __name__ == "__main__":
    main()
