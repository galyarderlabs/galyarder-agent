from typing import Iterable
from g_agent.memory.types import MemoryFragment

def format_memory_context(fragments: Iterable[MemoryFragment]) -> str:
    """Format memory fragments into a fenced XML-like block for the prompt."""
    if not fragments:
        return ""
        
    lines = ["<memory-context>"]
    for f in fragments:
        source_label = f"source: {f.source}"
        if f.metadata.get("type"):
            source_label += f", type: {f.metadata['type']}"
        if f.metadata.get("confidence"):
            source_label += f", confidence: {f.metadata['confidence']:.2f}"
            
        lines.append(f"  <!-- {source_label} -->")
        # Strip any nested memory tags from the content to prevent injection or confusion
        clean_content = f.content.replace("<memory-context>", "").replace("</memory-context>", "")
        lines.append(f"  {clean_content}")
        
    lines.append("</memory-context>")
    return "\n".join(lines)
