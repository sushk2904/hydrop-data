import os

def main():
    inp_path = "../data/drainage/mumbai_synthetic.inp"
    
    with open(inp_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    conduits_idx = -1
    junctions_idx = -1
    
    for i, line in enumerate(lines):
        if line.startswith("[CONDUITS]"):
            conduits_idx = i
        elif line.startswith("[JUNCTIONS]"):
            junctions_idx = i
            
    # Extract sources and destinations
    sources = set()
    destinations = set()
    
    for i in range(conduits_idx + 2, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if line.startswith("["):
            break
            
        parts = line.split()
        if len(parts) >= 3:
            sources.add(parts[1])
            destinations.add(parts[2])
            
    terminal_nodes = destinations - sources
    print(f"Found {len(terminal_nodes)} terminal nodes to convert to outfalls.")
    
    # Parse junctions and split
    new_junctions = []
    outfalls = []
    
    j_start = junctions_idx + 2
    j_end = j_start
    for i in range(j_start, len(lines)):
        if lines[i].startswith("["):
            j_end = i
            break
        j_end = i + 1
        
    for i in range(j_start, j_end):
        line = lines[i].strip()
        if not line:
            continue
        parts = line.split()
        node_id = parts[0]
        elevation = parts[1]
        
        if node_id in terminal_nodes:
            outfalls.append(f"{node_id} {elevation} FREE NO\n")
        else:
            new_junctions.append(lines[i])
            
    # Rewrite the file
    new_lines = []
    i = 0
    while i < len(lines):
        if i == junctions_idx:
            new_lines.append("[JUNCTIONS]\n")
            new_lines.append(";;Name Elevation MaxDepth InitDepth SurDepth Aponded\n")
            new_lines.extend(new_junctions)
            new_lines.append("\n[OUTFALLS]\n")
            new_lines.append(";;Name Elevation Type Stage Data Gated\n")
            new_lines.extend(outfalls)
            new_lines.append("\n")
            i = j_end
            continue
            
        new_lines.append(lines[i])
        i += 1
        
    with open(inp_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    print("Outfalls patch complete.")

if __name__ == "__main__":
    main()
