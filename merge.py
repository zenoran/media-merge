#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import shutil
import shlex

# Global flag for forced (non-interactive) mode.
force_mode = False

# Use readline to prefill input if available; in force mode, return the default.
def input_prefill(prompt, default):
    if force_mode:
        print(f"{prompt}{default}  [AUTO-ACCEPTED]")
        return default
    try:
        import readline
    except ImportError:
        return input(prompt)
    def hook():
        readline.insert_text(default)
        readline.redisplay()
    readline.set_pre_input_hook(hook)
    try:
        return input(prompt)
    finally:
        readline.set_pre_input_hook(None)

def get_size(path):
    """Return the size (in bytes) of a file or cumulative size of a directory."""
    total = 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except Exception:
                pass
    return total

def generate_rm_command(path):
    """Return an rm command for the given path (properly escaped).
       If its size is over 1GB, return a comment instead."""
    size = get_size(path)
    if size > 1073741824:
        return "# Skipped deletion of {} (size: {} bytes) as it is over 1GB".format(shlex.quote(path), size)
    return "rm -rf {}".format(shlex.quote(path))

def safe_move(src, dst):
    """Recursively move src to dst. If both exist as directories, merge them."""
    if not os.path.exists(dst):
        shutil.move(src, dst)
    else:
        if os.path.isdir(src) and os.path.isdir(dst):
            for item in os.listdir(src):
                safe_move(os.path.join(src, item), os.path.join(dst, item))
            try:
                os.rmdir(src)
            except Exception:
                pass
        else:
            print("\tSkipping {} because destination {} exists".format(src, dst))

def normalize_name(name):
    """
    Returns a canonical folder name in the form "Title (Year)".
      - Removes content in square brackets.
      - Replaces dots with spaces and collapses extra whitespace.
      - CASE 1: If the cleaned name starts with two 4-digit numbers, uses them.
      - CASE 2: Otherwise, captures everything up to the first 4-digit year and strips trailing whitespace or '('.
    """
    name_clean = re.sub(r'\[.*?\]', '', name)
    name_clean = name_clean.replace('.', ' ')
    name_clean = re.sub(r'\s+', ' ', name_clean).strip()
    m_num = re.match(r'^(\d{4})\s*\(?\s*(\d{4})\s*\)?$', name_clean)
    if m_num:
        return "{} ({})".format(m_num.group(1), m_num.group(2))
    m = re.search(r'^(.*?)\s*\(?\s*\b(19\d{2}|20\d{2})\b\)?', name_clean)
    if m:
        title = re.sub(r'[\s(]+$', '', m.group(1).strip())
        year = m.group(2)
        if title == "":
            return name_clean
        return "{} ({})".format(title, year)
    return name_clean

def tv_normalize_name(name):
    """
    For TV media, returns the base title by taking the normalized name and stripping any trailing " (YYYY)".
    This is used for grouping TV folders.
    """
    norm = normalize_name(name)
    tv_norm = re.sub(r'\s*\(\d{4}\)$', '', norm).strip()
    return tv_norm if tv_norm != "" else norm

def prompt_rename(folder, canonical, folder_path, target_dir):
    if force_mode:
        print(f"\tAutomatically renaming '{folder}' to '{canonical}'")
        new_name = canonical
    else:
        prompt = "Rename: {} -> ".format(folder)
        new_name = input_prefill(prompt, canonical).strip()
        if new_name.lower() == "s":
            print("\tSkipping rename for '{}'".format(folder))
            return
        if new_name == "":
            new_name = canonical
    new_path = os.path.join(target_dir, new_name)
    os.rename(folder_path, new_path)
    print("\tRenamed '{}' to '{}'".format(folder, new_name))

def prompt_merge(src_folder, dst_folder, src_path, dst_path):
    if force_mode:
        print(f"\tAutomatically merging '{src_folder}' into '{dst_folder}'")
    else:
        prompt = "Merge: {} into {}? (Enter=merge, 's'=skip): ".format(src_folder, dst_folder)
        ans = input(prompt).strip().lower()
        if ans == "s":
            print("\tSkipping merge for '{}'".format(src_folder))
            return
    for item in os.listdir(src_path):
        safe_move(os.path.join(src_path, item), os.path.join(dst_path, item))
    try:
        os.rmdir(src_path)
    except Exception:
        pass
    print("\tMerged '{}' into '{}'".format(src_folder, dst_folder))

def rename_and_merge(target_dir, media_type):
    print("=== Renaming/Merging Section ===")
    if media_type == "tv":
        print("(TV: Grouping by title; folders with a trailing year are preferred as canonical.)")
        groups = {}
        folders = [f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))]
        for folder in folders:
            base = tv_normalize_name(folder)
            groups.setdefault(base, []).append(folder)
        for base, group in groups.items():
            if len(group) < 2:
                continue
            # Prefer the folder that ends with " (YYYY)" as canonical.
            canonical_folder = None
            for folder in group:
                if re.search(r'\(\d{4}\)$', folder):
                    canonical_folder = folder
                    break
            if canonical_folder is None:
                canonical_folder = group[0]
            canonical_path = os.path.join(target_dir, canonical_folder)
            for folder in group:
                if folder == canonical_folder:
                    continue
                folder_path = os.path.join(target_dir, folder)
                prompt_merge(folder, canonical_folder, folder_path, canonical_path)
    else:
        print("(For renaming: press Enter to accept default, type a new name, or 's' to skip.)")
        print("(For merging: press Enter to merge, or 's' to skip.)\n")
        folders = [f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))]
        for folder in folders:
            folder_path = os.path.join(target_dir, folder)
            canonical = normalize_name(folder)
            canonical_path = os.path.join(target_dir, canonical)
            if folder == canonical:
                continue
            if os.path.isdir(canonical_path):
                prompt_merge(folder, canonical, folder_path, canonical_path)
            else:
                prompt_rename(folder, canonical, folder_path, target_dir)

def determine_media_type(target_dir):
    base = os.path.basename(os.path.normpath(target_dir)).lower()
    if "movie" in base or "movies" in base:
        return "movie"
    if "tv" in base or "show" in base:
        return "tv"
    for folder in os.listdir(target_dir):
        folder_path = os.path.join(target_dir, folder)
        if os.path.isdir(folder_path):
            for subfolder in os.listdir(folder_path):
                if re.search(r'season', subfolder, re.I) or re.match(r's\d+', subfolder, re.I):
                    return "tv"
    if force_mode:
        print("Media type undetermined. Defaulting to MOVIE in forced mode.")
        return "movie"
    answer = input("Media type undetermined. Is this a TV directory? (y/n): ").strip().lower()
    return "tv" if answer.startswith("y") else "movie"

def gather_movie_cleanup_commands(target_dir):
    allowed_ext = ['.mkv', '.mp4', '.avi', '.mov', '.m4v', '.wmv', '.iso']
    commands = []
    folders = [f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))]
    for folder in folders:
        folder_path = os.path.join(target_dir, folder)
        items = os.listdir(folder_path)
        full_paths = [os.path.join(folder_path, item) for item in items]
        video_files = [p for p in full_paths if os.path.isfile(p) and os.path.splitext(p)[1].lower() in allowed_ext]
        if not video_files:
            commands.append(generate_rm_command(folder_path))
            continue
        if len(full_paths) == 1 and video_files:
            continue
        main_video = max(video_files, key=lambda p: os.path.getsize(p))
        for p in full_paths:
            if p == main_video:
                continue
            commands.append(generate_rm_command(p))
    return commands

def gather_tv_cleanup_commands(target_dir):
    allowed_ext = ['.mkv', '.mp4', '.avi', '.mov', '.m4v', '.wmv', '.iso']
    commands = []
    for show in os.listdir(target_dir):
        show_path = os.path.join(target_dir, show)
        if not os.path.isdir(show_path):
            continue
        season_found = False
        for sub in os.listdir(show_path):
            season_path = os.path.join(show_path, sub)
            if os.path.isdir(season_path) and (re.search(r'season', sub, re.I) or re.match(r's\d+', sub, re.I)):
                season_found = True
                for item in os.listdir(season_path):
                    item_path = os.path.join(season_path, item)
                    if os.path.isfile(item_path):
                        ext = os.path.splitext(item)[1].lower()
                        if ext not in allowed_ext:
                            commands.append(generate_rm_command(item_path))
                    else:
                        commands.append(generate_rm_command(item_path))
        if not season_found:
            items = os.listdir(show_path)
            full_paths = [os.path.join(show_path, item) for item in items]
            video_files = [p for p in full_paths if os.path.isfile(p) and os.path.splitext(p)[1].lower() in allowed_ext]
            if not video_files:
                commands.append(generate_rm_command(show_path))
            elif len(full_paths) > 1:
                main_video = max(video_files, key=lambda p: os.path.getsize(p))
                for p in full_paths:
                    if p == main_video:
                        continue
                    commands.append(generate_rm_command(p))
    return commands

def create_cleanup_script(target_dir, commands):
    if not commands:
        return None
    cleanup_script = os.path.join(target_dir, "cleanup.sh")
    with open(cleanup_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n\n")
        for cmd in commands:
            f.write(cmd + "\n")
    os.chmod(cleanup_script, 0o755)
    return cleanup_script

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python merge.py <target_folder> [--force|-f]")
        sys.exit(1)
    target_dir = os.path.abspath(sys.argv[1])
    if len(sys.argv) >= 3 and sys.argv[2] in ("--force", "-f"):
        force_mode = True
    
    print("Starting folder normalization and cleanup process in:")
    print("\t" + target_dir + "\n")
    
    media_type = determine_media_type(target_dir)
    print("Detected media type: {}\n".format(media_type.upper()))
    
    # Step 1: Rename and/or merge top-level folders.
    rename_and_merge(target_dir, media_type)
    
    # Step 2: Gather cleanup commands.
    print("\n=== Cleanup Section ===")
    if media_type == "movie":
        cleanup_commands = gather_movie_cleanup_commands(target_dir)
    else:
        cleanup_commands = gather_tv_cleanup_commands(target_dir)
    
    if cleanup_commands:
        cleanup_script = create_cleanup_script(target_dir, cleanup_commands)
        if cleanup_script:
            print("\tCleanup script created: {}".format(cleanup_script))
            print("\tReview the script and run it manually to remove extra files/folders.")
        else:
            print("\tNo cleanup script created (no extra files detected).")
    else:
        print("\tNo extra files/folders detected in {} folders.".format(media_type))
    
    print("\nProcess complete.")
