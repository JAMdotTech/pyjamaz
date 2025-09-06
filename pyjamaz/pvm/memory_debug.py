#!/usr/bin/env python3
"""
Memory debugging utilities for PVM interpreters
"""
import hashlib
import numpy as np
from typing import Dict, Any, Optional


def hash_memory_segment(contents: Any) -> str:
    """
    Create a deterministic hash of memory contents
    """
    if contents is None:
        return "none"
    
    # Convert to bytes if needed
    if isinstance(contents, np.ndarray):
        data = contents.tobytes()
    elif isinstance(contents, (bytes, bytearray)):
        data = bytes(contents)
    else:
        # Try to convert to bytes
        try:
            data = bytes(contents)
        except:
            data = str(contents).encode('utf-8')
    
    # Create SHA256 hash
    return hashlib.sha256(data).hexdigest()[:16]  # First 16 chars for brevity


def get_memory_hash(pvm_memory) -> Dict[str, Any]:
    """
    Get a hash representation of PVM memory state
    
    Args:
        pvm_memory: PVMMemory object or None
        
    Returns:
        Dict with memory segment info and hashes
    """
    if pvm_memory is None:
        return {"status": "no_memory"}
    
    result = {
        "status": "ok",
        "segments": {},
        "acl": {}
    }
    
    # Process each memory segment
    segments = [
        ("rom", pvm_memory._rom),
        ("heap", pvm_memory._heap),
        ("stack", pvm_memory._stack),
        ("args", pvm_memory._args)
    ]
    
    for name, segment in segments:
        if segment is None:
            result["segments"][name] = {
                "exists": False
            }
        else:
            # Get segment properties
            segment_info = {
                "address": hex(segment.address),
                "size": segment.size,
                "paged_tail": hex(segment.paged_tail),
                "actual_tail_offset": int(segment.paged_tail - segment.address),
                "content_length": len(segment.contents) if hasattr(segment.contents, '__len__') else 0,
                "content_hash": hash_memory_segment(segment.contents),
                "acl": segment.acl.value if hasattr(segment.acl, 'value') else segment.acl
            }
            
            # Add first and last few bytes for debugging
            if hasattr(segment.contents, '__getitem__') and len(segment.contents) > 0:
                # First 32 bytes
                # first_bytes = []
                # for i in range(min(32, len(segment.contents))):
                #     first_bytes.append(segment.contents[i])
                # segment_info["first_32_bytes"] = bytes(first_bytes).hex()
                
                # Last 32 bytes
                # if len(segment.contents) > 32:
                #     last_bytes = []
                #     start = max(0, len(segment.contents) - 32)
                #     for i in range(start, len(segment.contents)):
                #         last_bytes.append(segment.contents[i])
                #     segment_info["last_32_bytes"] = bytes(last_bytes).hex()
                
                # Check for non-zero content
                non_zero_count = 0
                for i in range(min(1000, len(segment.contents))):
                    if segment.contents[i] != 0:
                        non_zero_count += 1
                segment_info["non_zero_in_first_1000"] = non_zero_count
            
            result["segments"][name] = segment_info
    
    # Process ACL if available
    if hasattr(pvm_memory, '_acl') and pvm_memory._acl:
        result["acl"]["page_count"] = len(pvm_memory._acl)
        result["acl"]["pages"] = {}
        
        # Sample some ACL entries
        for page_nr in sorted(pvm_memory._acl.keys())[:10]:  # First 10 pages
            result["acl"]["pages"][page_nr] = pvm_memory._acl[page_nr]
    
    return result


def compare_memory_hashes(hash1: Dict[str, Any], hash2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two memory hash dictionaries and report differences
    """
    differences = {
        "identical": True,
        "differences": []
    }
    
    # Compare segment existence
    for segment_name in ["rom", "heap", "stack", "args"]:
        seg1 = hash1.get("segments", {}).get(segment_name, {})
        seg2 = hash2.get("segments", {}).get(segment_name, {})
        
        if seg1.get("exists") != seg2.get("exists"):
            differences["identical"] = False
            differences["differences"].append({
                "segment": segment_name,
                "type": "existence",
                "value1": seg1.get("exists"),
                "value2": seg2.get("exists")
            })
            continue
        
        if not seg1.get("exists"):
            continue
        
        # Compare properties
        props_to_compare = ["address", "size", "paged_tail", "content_hash", "acl"]
        for prop in props_to_compare:
            if seg1.get(prop) != seg2.get(prop):
                differences["identical"] = False
                differences["differences"].append({
                    "segment": segment_name,
                    "type": prop,
                    "value1": seg1.get(prop),
                    "value2": seg2.get(prop)
                })
    
    return differences


def print_memory_hash(pvm_memory, label: str = "Memory State") -> None:
    """
    Print a formatted memory hash for debugging
    """
    hash_data = get_memory_hash(pvm_memory)
    
    print(f"\n=== {label} ===")
    
    if hash_data["status"] == "no_memory":
        print("No memory allocated")
        return
    
    for segment_name, segment_data in hash_data["segments"].items():
        if not segment_data["exists"]:
            print(f"\n{segment_name.upper()}: Not allocated")
            continue
        
        print(f"\n{segment_name.upper()}:")
        print(f"  Address:     {segment_data['address']}")
        print(f"  Size:        {segment_data['size']} bytes")
        print(f"  Paged tail:  {segment_data['paged_tail']}")
        print(f"  Tail offset: {segment_data['actual_tail_offset']} bytes")
        print(f"  Content len: {segment_data['content_length']} bytes")
        print(f"  Hash:        {segment_data['content_hash']}")
        print(f"  ACL:         {segment_data['acl']}")
        
        if segment_data.get('non_zero_in_first_1000', 0) > 0:
            print(f"  Non-zero:    {segment_data['non_zero_in_first_1000']} bytes in first 1000")
        
        # if 'first_32_bytes' in segment_data:
        #     print(f"  First bytes: {segment_data['first_32_bytes'][:32]}...")
    
    if hash_data.get("acl", {}).get("page_count"):
        print(f"\nACL: {hash_data['acl']['page_count']} pages")


def debug_memory_at_pc(pvm_interpreter, pc: Optional[int] = None) -> Dict[str, Any]:
    """
    Capture memory state at a specific PC for debugging
    """
    if pc is None:
        pc = pvm_interpreter.pc
    
    result = {
        "pc": pc,
        "gas": int(pvm_interpreter.gas) if hasattr(pvm_interpreter, 'gas') else None,
        "status": int(pvm_interpreter.status) if hasattr(pvm_interpreter, 'status') else None,
        "memory_hash": get_memory_hash(pvm_interpreter.mem if hasattr(pvm_interpreter, 'mem') else None)
    }
    
    # Add registers
    if hasattr(pvm_interpreter, 'reg'):
        result["registers"] = [int(r) for r in pvm_interpreter.reg]
    
    return result


if __name__ == "__main__":
    # Test the memory hash functions
    from pyjamaz.pvm.types_new import PVMMemory, MemorySection, PVMMemoryMode
    import numpy as np
    
    # Create test memory
    test_section = MemorySection(
        address=0x10000,
        size=4096,
        contents=np.zeros(4096, dtype=np.uint8),
        acl=PVMMemoryMode.writable
    )
    
    # Write some test data
    test_section.contents[0] = 0x12
    test_section.contents[1] = 0x34
    test_section.contents[2] = 0x56
    test_section.contents[3] = 0x78
    
    test_memory = PVMMemory(
        rom=None,
        heap=test_section,
        stack=None,
        arguments=None
    )
    
    # Test hash function
    print_memory_hash(test_memory, "Test Memory")
    
    # Get hash
    hash_data = get_memory_hash(test_memory)
    print(f"\nHash data structure:")
    import json
    print(json.dumps(hash_data, indent=2))