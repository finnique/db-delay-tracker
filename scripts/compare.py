from lxml import etree
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

rchg_files = sorted(FIXTURES_DIR.glob("rchg_*.xml"))
fchg_files = sorted(FIXTURES_DIR.glob("fchg_*.xml"))

TARGET_EVAS = {"8000261", "8003092"}
# TARGET_EVAS = {"8000261"}

def load_stops(path):
    root = etree.parse(path).getroot()
    ids = {s.get("id"): s for s in root.iter("s")}
    return ids

for eva_num in TARGET_EVAS:
    print(f"EVA: {eva_num}")
    count = 1
    ids_combined = {} # [len(r1), len(r2), len(f)]

    for path in rchg_files:
        eva_path = path.stem.split("_")[1]

        if eva_path == eva_num:  
            ids = load_stops(path)
            key_name = f"r{count}"
            ids_combined[key_name] = ids
            count += 1

    for path in fchg_files:
        eva_path = path.stem.split("_")[1]

        if eva_path == eva_num:
            ids_combined["F"] = load_stops(path)


    print("---Check 1: size")
    for item in ids_combined:
        print(f"{item}: {len(ids_combined.get(item))}")

    print("---Check 2: subset")
    r1_only = set(ids_combined.get("r1")) - set(ids_combined.get("F"))
    print(r1_only)

    print("---Check 3: same stop, same content?")
    f = ids_combined.get("F")
    same_count = {"True": [], "False": []}

    for round in ["r1", "r2"]:
        target_round = ids_combined.get(round)
        # print(f"target round: {target_round}")
        # print(f"F: {f}")

        for stop_id in set(target_round) & set(f):
            same = etree.tostring(target_round[stop_id], with_tail=False) == etree.tostring(f[stop_id], with_tail=False)

            if same is True:
                same_count["True"].append(stop_id)
            else: 
                same_count["False"].append(stop_id)

        print(f"Round: {round}")
        print(f"True: {len(same_count["True"])}")
        # print(same_count["True"])

        print(f"False: {len(same_count["False"])}")
        print(same_count["False"])
    
    print("---Check 4: r1 vs r2")
    r1, r2 = ids_combined["r1"], ids_combined["r2"]
    print("in both:", len(set(r1) & set(r2)))
    print("new in r2:", len(set(r2) - set(r1)))
    print("dropped from r1:", len(set(r1) - set(r2)))

    print("==================")
    
        # print(same)




# tree = etree.parse("tests/fixtures/rchg_8000261_HHMMSS.xml")
# ids = {s.get("id") for s in tree.getroot().iter("s")}
