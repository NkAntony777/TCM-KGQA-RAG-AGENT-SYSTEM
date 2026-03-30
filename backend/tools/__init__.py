from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool

def _safe_add(tools: list[BaseTool], factory, errors: list[str]) -> None:
    try:
        tools.append(factory())
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        errors.append(str(exc))


def get_all_tools(base_dir: Path) -> list[BaseTool]:
    tools: list[BaseTool] = []
    load_errors: list[str] = []

    from tools.fetch_url_tool import FetchURLTool
    from tools.python_repl_tool import PythonReplTool
    from tools.read_file_tool import ReadFileTool
    from tools.terminal_tool import TerminalTool

    # Base tooling (expected to always be available)
    tools.append(TerminalTool(root_dir=base_dir))
    tools.append(PythonReplTool(root_dir=base_dir))
    tools.append(FetchURLTool())
    tools.append(ReadFileTool(root_dir=base_dir))

    # TCM fusion tools (S0 integration)
    from tools.tcm_graph_tools import TCMEntityLookupTool, TCMPathQueryTool, TCMSyndromeChainTool
    from tools.tcm_retrieval_tools import TCMHybridSearchTool, TCMRewriteTool
    from tools.tcm_route_tool import TCMRouteSearchTool

    tools.append(TCMRouteSearchTool())
    tools.append(TCMEntityLookupTool())
    tools.append(TCMPathQueryTool())
    tools.append(TCMSyndromeChainTool())
    tools.append(TCMHybridSearchTool())
    tools.append(TCMRewriteTool())

    # Optional legacy/local-knowledge tool: keep non-blocking on missing deps.
    def _knowledge_factory():
        from tools.search_knowledge_tool import SearchKnowledgeBaseTool

        return SearchKnowledgeBaseTool(root_dir=base_dir)

    _safe_add(tools, _knowledge_factory, load_errors)

    # Keep diagnostics lightweight and non-fatal.
    if load_errors:
        print(f"[tools] optional tools skipped: {load_errors}")

    return tools
