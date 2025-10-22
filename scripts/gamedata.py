import argparse
import json
import os
import requests
import shutil
import subprocess

flatbuffer_list = [
    "activity_table",
    "audio_data",
    "battle_equip_table",
    "buff_table",
    "building_data",
    "campaign_table",
    "chapter_table",
    "char_master_table",
    "char_meta_table",
    "char_patch_table",
    "character_table",
    "charm_table",
    "charword_table",
    "checkin_table",
    "climb_tower_table",
    "clue_data",
    "crisis_table",
    "crisis_v2_table",
    "display_meta_table",
    "enemy_database",
    "enemy_handbook_table",
    "favor_table",
    "gacha_table",
    "gamedata_const",
    "handbook_info_table",
    "handbook_team_table",
    "hotupdate_meta_table",
    "item_table",
    "level_script_table",
    "medal_table",
    "meta_ui_table",
    "mission_table",
    "open_server_table",
    "replicate_table",
    "retro_table",
    "roguelike_topic_table",
    "sandbox_perm_table",
    "shop_client_table",
    "skill_table",
    "skin_table",
    "special_operator_table",
    "stage_table",
    "story_review_meta_table",
    "story_review_table",
    "story_table",
    "tip_table",
    "token_table",
    "uniequip_table",
    "zone_table",
    "cooperate_battle_table",
    "ep_breakbuff_table",
    "extra_battlelog_table",
    "legion_mode_buff_table",
    "building_local_data",
]

flatbuffer_mappings = {
    "level_": "prts___levels",
}


commits_page_cache = []


def get_commits_page(page):
    if page <= len(commits_page_cache) and commits_page_cache[page - 1]:
        # print(f"Fetching cached data for FB commits page {page}")
        return commits_page_cache[page - 1]
    # print(f"Fetching data for FB commits page {page}")
    response = requests.get(f"https://api.github.com/repos/MooncellWiki/OpenArknightsFBS/commits?sha=main&page={page}&per_page=100")
    commits = response.json()
    commits_page_cache.append(commits)
    return commits


def get_flatbuffer_name(path: str) -> str | None:
    matched = [
        *[flatbuffer for flatbuffer in flatbuffer_list if flatbuffer == path],
        *[flatbuffer for mapping, flatbuffer in flatbuffer_mappings.items() if mapping in path],
    ]
    return matched[0] if matched else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-dir", default="./flatbuffers", help="Path to flatbuffer schema directory")
    parser.add_argument("--anon-dir", default="./temp/extract/anon", help="Path to anon directory")
    parser.add_argument("--obb-dir", default="./temp/extract/obb", help="Path to obb directory")
    parser.add_argument("--merge-dir", default="./temp/merge", help="Path to merge directory")
    parser.add_argument("--out-dir", default="./gamedata", help="Path to output directory")
    args = parser.parse_args()

    files = {}
    for dir_path in [args.anon_dir, args.obb_dir]:
        for root, _, fnames in os.walk(dir_path):
            for fname in fnames:
                if not fname.endswith(".bytes"):
                    continue
                base = fname[:-6]  # strip ".bytes"
                core = None
                if get_flatbuffer_name(base):
                    core = base
                elif len(base) > 6 and get_flatbuffer_name(base[:-6]):
                    core = base[:-6]
                else:
                    print(f"Unknown FBS schema '{fname}'")
                    continue
                if core in files:
                    continue
                full_path = os.path.join(root, fname)
                dst_path = os.path.relpath(os.path.join(root, core + ".bytes"), dir_path)
                files[core] = (full_path, dst_path)

    for core, (src, dst_path) in files.items():
        dst = os.path.join(args.merge_dir, dst_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            fsrc.seek(128)  # trim first 128 bytes
            shutil.copyfileobj(fsrc, fdst)
            # print(f"Trimmed & copied {src} -> {dst}")

    with open(os.path.join(args.schema_dir, "_flatbuffers.json"), "r") as f:
        _flatbuffers = json.load(f)

    for root, _, fnames in os.walk(args.merge_dir):
        for fname in fnames:
            if not fname.endswith(".bytes"):
                continue

            base = fname[:-6]
            schema = get_flatbuffer_name(base)
            if not schema:
                print(f"Unknown schema for {fname}, skipping")
                continue
            schema_file = f"{schema}.fbs"

            src_path = os.path.join(root, fname)
            rel_path = os.path.relpath(src_path, args.merge_dir)
            out_subdir = os.path.join(args.out_dir, os.path.dirname(rel_path))
            os.makedirs(out_subdir, exist_ok=True)

            def deserialize():
                result = subprocess.run([
                    "flatc",
                    "-o", out_subdir,
                    "--no-warnings",
                    "--json",
                    "--strict-json",
                    "--natural-utf8",
                    "--defaults-json",
                    "--raw-binary",
                    os.path.join(args.schema_dir, schema_file),
                    "--",
                    src_path
                ])
                # print(" ".join([
                #     "flatc",
                #     "-o", out_subdir,
                #     "--no-warnings",
                #     "--json",
                #     "--strict-json",
                #     "--natural-utf8",
                #     "--defaults-json",
                #     "--raw-binary",
                #     os.path.join(args.schema_dir, schema_file),
                #     "--",
                #     src_path
                # ]))
                # print(result.returncode)
                return True

            def validate(commit):
                json_file_path = os.path.join(out_subdir, base + ".json")
                # print(out_subdir)
                # print(json_file_path)
                if not os.path.exists(json_file_path):
                    return False
                with open(json_file_path, 'r') as json_file:
                    try:
                        parsed_json = json.load(json_file)
                        if _flatbuffers[schema_file]['commit'] != commit:
                            _flatbuffers[schema_file]['commit'] = commit
                            print(f"Validated {schema_file} at {commit}")
                        return True
                    except Exception as e:
                        # print(f"Error decoding JSON for {json_file_path}: {e}")
                        return False

            def find_next_commit(commit):
                page = 1
                while True:
                    commits = get_commits_page(page)
                    if not commits:
                        print(f"Error finding next commit at {commit}")
                        return False
                    parent_commits = [x for x in commits if x['parents'] and x['parents'][0]['sha'] == commit]
                    if parent_commits:
                        return parent_commits[0]['sha']
                    else:
                        page += 1

            def replace_schema(commit):
                try:
                    response = requests.get(f"https://raw.githubusercontent.com/MooncellWiki/OpenArknightsFBS/{commit}/FBS/{schema}.fbs")
                    with open(os.path.join(args.schema_dir, schema_file), "w") as f:
                        f.write(response.text)
                    return True
                except Exception as e:
                    print(f"Error replacing {schema_file}: {e}")
                    return False

            # print(schema_file)
            current_commit = _flatbuffers[schema_file]['commit']
            while deserialize() and not validate(current_commit):
                next_commit = find_next_commit(current_commit)
                if (next_commit):
                    replace_schema(next_commit)
                    current_commit = next_commit
                else:
                    break

    with open(os.path.join(args.schema_dir, "_flatbuffers.json"), "w") as f:
        f.write(json.dumps(_flatbuffers, indent=4))


if __name__ == "__main__":
    main()
