"""
Interactive Colab Launcher for the DTM, Hydrology, and LULC pipelines.
"""

import os
import subprocess
import sys
import glob

def discover_datasets(input_dir, output_dir):
    unprocessed = []
    if os.path.exists(input_dir):
        unprocessed.extend(glob.glob(os.path.join(input_dir, "**", "*.la[sz]"), recursive=True))
        unprocessed.extend(glob.glob(os.path.join(input_dir, "**", "*.LA[SZ]"), recursive=True))
        
    processed = []
    if os.path.exists(output_dir):
        processed = [d for d in glob.glob(os.path.join(output_dir, "*")) if os.path.isdir(d)]
        
    return unprocessed, processed

def print_menu(datasets):
    print("\n" + "="*50)
    print("  PIPELINE LAUNCHER")
    print("="*50)
    print("Available Datasets:")
    for i, name in enumerate(datasets, 1):
        print(f"  {i:>2}. {name}")
    print(f"  {len(datasets) + 1:>2}. ALL DATASETS")
    print("="*50)

def ask_process():
    print("\nSelect Process to Run:")
    print("  1. DTM & Drainage Pipeline")
    print("  2. Hydrology Pipeline")
    print("  3. LULC Pipeline")
    print("  4. ALL PROCESSES")
    
    choice = input("Enter choice (1-4): ").strip()
    return choice

def run_process(script_name, village_name):
    print(f"\n" + "-"*50)
    print(f"---> Executing {script_name} for {village_name}...")
    print("-"*50)
    cmd = [sys.executable, script_name, village_name]
    subprocess.run(cmd)

def main():
    base_dir = os.environ.get("BASE_DIR", os.path.abspath(os.path.dirname(__file__)))
    input_dir = os.environ.get("INPUTS_DIR", os.path.join(base_dir, "input_data"))
    output_dir = os.environ.get("OUTPUTS_DIR", os.path.join(base_dir, "outputs"))
    
    unprocessed, processed = discover_datasets(input_dir, output_dir)
    
    # Extract unique names
    all_names = set()
    for p in unprocessed:
        all_names.add(os.path.splitext(os.path.basename(p))[0])
    for p in processed:
        all_names.add(os.path.basename(p))
        
    dataset_list = sorted(list(all_names))
    
    if not dataset_list:
        print("No datasets found in input_data or outputs directories.")
        return

    while True:
        print_menu(dataset_list)
        vill_choice = input(f"Select Dataset (1-{len(dataset_list) + 1}) or 'q' to quit: ").strip()
        
        if vill_choice.lower() == 'q':
            break
            
        try:
            vi = int(vill_choice)
            if 1 <= vi <= len(dataset_list):
                selected_villages = [dataset_list[vi-1]]
            elif vi == len(dataset_list) + 1:
                selected_villages = dataset_list
            else:
                print("Invalid choice. Try again.")
                continue
        except ValueError:
            print("Invalid input. Try again.")
            continue
            
        proc_choice = ask_process()
        if proc_choice not in ["1", "2", "3", "4"]:
            print("Invalid process choice. Try again.")
            continue
            
        scripts = []
        if proc_choice in ["1", "4"]:
            scripts.append("GEO_INTEL_pipeline.py")
        if proc_choice in ["2", "4"]:
            scripts.append("Hydrology_pipeline.py")
        if proc_choice in ["3", "4"]:
            scripts.append("lulc_pipeline.py")
            
        for vill in selected_villages:
            for script in scripts:
                # If script doesn't exist, log warning
                if not os.path.exists(os.path.join(base_dir, script)):
                    print(f"Warning: Script {script} not found in {base_dir}")
                    continue
                run_process(os.path.join(base_dir, script), vill)

        print("\n" + "="*50)
        print("  PIPELINE EXECUTION COMPLETE")
        print("="*50 + "\n")

if __name__ == "__main__":
    main()
