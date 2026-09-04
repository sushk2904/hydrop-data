import os

def main():
    inp_path = "../data/drainage/mumbai_synthetic.inp"
    print("Reading .inp file to patch Error 141...")
    
    with open(inp_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Group lines by SWMM section
    sections = {}
    current_sec = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_sec = stripped
            sections[current_sec] = []
        elif current_sec:
            sections[current_sec].append(line)

    # 1. Count how many pipes flow into each node
    inlet_counts = {}
    for line in sections.get("[CONDUITS]", []):
        parts = line.split()
        if len(parts) >= 3 and not line.startswith(";"):
            dst = parts[2]
            inlet_counts[dst] = inlet_counts.get(dst, 0) + 1

    # 2. Identify the rule-breaking outfalls
    valid_outfalls = []
    invalid_outfalls = []
    for line in sections.get("[OUTFALLS]", []):
        parts = line.split()
        if len(parts) >= 2 and not line.startswith(";"):
            node = parts[0]
            if inlet_counts.get(node, 0) > 1:
                invalid_outfalls.append(parts)
            else:
                valid_outfalls.append(line)
        else:
            valid_outfalls.append(line)

    sections["[OUTFALLS]"] = valid_outfalls
    print(f"Found {len(invalid_outfalls)} outfalls with multiple inlets. Applying dummy links...")

    # 3. Patch the network
    for parts in invalid_outfalls:
        node = parts[0]
        elev = float(parts[1])
        
        # Revert back to a normal junction
        sections["[JUNCTIONS]"].append(f"{node} {elev:.2f} 0 0 0 0\n")
        
        # Create a dedicated 1-to-1 dummy outfall (slightly lower to force gravity flow)
        dummy_out = f"OUT_{node}"
        sections["[OUTFALLS]"].append(f"{dummy_out} {elev - 0.1:.2f} FREE NO\n")
        
        # Connect them with a wide, short discharge pipe
        dummy_pipe = f"DUMMY_{node}"
        sections["[CONDUITS]"].append(f"{dummy_pipe} {node} {dummy_out} 10.0 0.013 0 0 0 0\n")
        
        # Assign a 1-meter circular shape to the dummy pipe
        if "[XSECTIONS]" not in sections:
            sections["[XSECTIONS]"] = [";;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels\n"]
        sections["[XSECTIONS]"].append(f"{dummy_pipe} CIRCULAR 1.0 0 0 0 1\n")

    # Write the repaired file back to disk
    with open(inp_path, "w", encoding="utf-8") as f:
        for sec, slines in sections.items():
            f.write(sec + "\n")
            f.writelines(slines)
            f.write("\n")
            
    print("Patch complete! The network is now hydraulically valid.")

if __name__ == "__main__":
    main()