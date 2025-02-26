import os                    # Handles file and directory operations
import shutil                # Checks if external tools (e.g., FFmpeg) are available
import subprocess            # Executes FFmpeg and ffprobe commands
import argparse              # Parses command-line arguments
import datetime              # Generates timestamps for log/output files
import json                  # Parses JSON output from ffprobe
from typing import List, Tuple  # Adds type hints for clarity
from pathlib import Path     # Modern path handling for cross-platform compatibility
import sys                   # Provides access to stdout for verbose output

# Define supported audio file extensions as a constant
AUDIO_EXTENSIONS = ['.flac', '.wav', '.m4a', '.mp3', '.ogg', '.opus', '.ape', '.wv', '.wma']
# Used across all functions to identify audio files consistently

def print_progress_bar(current: int, total: int, task_name: str = ''):
    """Displays a simple ASCII progress bar in the terminal.

    Args:
        current: The current step (e.g., files processed so far).
        total: The total number of steps (e.g., total files to process).
        task_name: A label describing the task (e.g., "Checking files").

    Behavior:
        - Shows a bar like "[#######----] 70% 7/10" with '#' for progress and '-' for remaining.
        - Updates in place using '\r' to overwrite the previous line.
        - Adds a newline when the task is complete to preserve the final state.
    """
    BAR_LENGTH = 70  # Fixed width of the progress bar in characters
    percentage = (current / total) * 100 if total > 0 else 100  # Avoid division by zero
    filled = int(BAR_LENGTH * current // total) if total > 0 else BAR_LENGTH  # Portion to fill
    bar = '#' * filled + '-' * (BAR_LENGTH - filled)  # Build the visual bar
    print(f'\r{task_name} [{bar}] {int(percentage)}% {current}/{total}', end='', flush=True)
    if current == total:
        print()  # Move to a new line when done

def directory_path(path: str) -> str:
    """Ensures a path is a valid directory for argparse.

    Args:
        path: The path to validate.

    Returns:
        The path if it’s a directory.

    Raises:
        argparse.ArgumentTypeError: If the path isn’t a directory.
    """
    if os.path.isdir(path):
        return path
    raise argparse.ArgumentTypeError(f"'{path}' is not a directory")

def path_type(path: str) -> str:
    """Ensures a path exists (file or directory) for argparse.

    Args:
        path: The path to validate.

    Returns:
        The path if it exists.

    Raises:
        argparse.ArgumentTypeError: If the path doesn’t exist.
    """
    if os.path.exists(path):
        return path
    raise argparse.ArgumentTypeError(f"'{path}' does not exist")

def get_audio_files(directory: str) -> List[str]:
    """Finds all audio files in a directory and its subdirectories.

    Args:
        directory: The root directory to search.

    Returns:
        A list of full paths to audio files with supported extensions.

    Logic:
        - Uses os.walk() to traverse the directory tree recursively.
        - Matches file extensions case-insensitively against AUDIO_EXTENSIONS.
    """
    audio_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                audio_files.append(os.path.join(root, file))
    return audio_files

def check_file_integrity(file_path: str) -> Tuple[str, str]:
    """Checks an audio file’s integrity using FFmpeg.

    Args:
        file_path: The path to the audio file.

    Returns:
        A tuple (status, message):
        - status: "PASSED" if no issues, "FAILED" if issues found.
        - message: Empty if passed, error details if failed.

    Logic:
        - Runs FFmpeg with '-v error' to log only errors and '-f null' to skip decoding.
        - Captures stderr to detect issues; empty stderr means the file is good.
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            capture_output=True, text=True
        )
        return ("PASSED", "") if not result.stderr else ("FAILED", result.stderr.strip())
    except Exception as e:
        return ("FAILED", str(e))  # Covers cases like FFmpeg not found

def check_integrity(path: str, verbose: bool = False, save_log: bool = False):
    """Verifies integrity of audio files in a path.

    Args:
        path: File or directory to check.
        verbose: If True, prints results to console without a progress bar.
        save_log: If True, saves results to a log file (default when not verbose).

    Behavior:
        - Processes a single file or all audio files in a directory.
        - Shows progress unless verbose is True.
        - Saves a log unless verbose=True and save_log=False.
    """
    # Verify FFmpeg is available
    if not shutil.which('ffmpeg'):
        print("Error: FFmpeg is not installed or not in your PATH.")
        return

    # Determine if path is a file or directory and collect audio files
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [path]
        else:
            print(f"'{path}' is not a supported audio file.")
            return
    elif os.path.isdir(path):
        audio_files = get_audio_files(path)
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        print(f"'{path}' is not a file or directory.")
        return

    # Prepare log file if needed
    log_file = None
    if save_log or not verbose:  # Log by default unless explicitly disabled with verbose
        log_filename = f"integrity_check_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')

    # Process files and track results
    passed_count = 0
    failed_count = 0
    total_files = len(audio_files)

    if not verbose:
        print_progress_bar(0, total_files, "Checking files")

    for index, file_path in enumerate(audio_files):
        status, message = check_file_integrity(file_path)
        result_line = f"{status} {file_path}" + (f": {message}" if message else "")

        # Output based on verbosity and logging settings
        if verbose:
            print(result_line)
        if log_file:
            log_file.write(result_line + "\n")

        # Update counts
        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

        if not verbose:
            print_progress_bar(index + 1, total_files, "Checking files")

    # Summarize results
    summary = f"\nSummary:\nTotal files: {total_files}\nPassed: {passed_count}\nFailed: {failed_count}\n"
    if verbose:
        print(summary)
    if log_file:
        log_file.write(summary)
        log_file.close()
        print(f"Check complete. Log saved to '{log_filename}'")
    else:
        print("Check complete.")

def rename_cover_art(file_path: str, hide: bool):
    """Renames cover art files to hide or show them.

    Args:
        file_path: The full path to the file.
        hide: True to add a dot prefix (hide), False to remove it (show).

    Logic:
        - Targets specific filenames: cover.jpg, cover.jpeg, cover.png.
        - Only renames if the target name doesn’t already exist.
    """
    file_name = os.path.basename(file_path)
    directory = os.path.dirname(file_path)

    if hide and file_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
        new_name = os.path.join(directory, "." + file_name)
        if not os.path.exists(new_name):
            os.rename(file_path, new_name)
    elif not hide and file_name in [".cover.jpg", ".cover.jpeg", ".cover.png"]:
        new_name = os.path.join(directory, file_name[1:])
        if not os.path.exists(new_name):
            os.rename(file_path, new_name)

def process_cover_art(path: str, hide: bool):
    """Processes cover art files in a directory.

    Args:
        path: Directory to process.
        hide: True to hide cover art, False to show it.

    Behavior:
        - Recursively finds and renames cover art files.
        - Shows progress with a bar.
    """
    total_files = sum(len(files) for _, _, files in os.walk(path))
    if total_files == 0:
        print(f"No files found in '{path}' to process.")
        return

    processed = 0
    print_progress_bar(processed, total_files, "Processing cover art")

    for root, _, files in os.walk(path):
        for file in files:
            rename_cover_art(os.path.join(root, file), hide)
            processed += 1
            print_progress_bar(processed, total_files, "Processing cover art")

def analyze_audio(path: str, output_stream, show_progress: bool = True):
    """Analyzes audio file metadata and writes results.

    Args:
        path: File or directory to analyze.
        output_stream: Where to write results (e.g., file or sys.stdout).
        show_progress: If True, displays a progress bar.

    Behavior:
        - Uses ffprobe to extract metadata like bitrate and codec.
        - Adds warnings for potential quality issues.
    """
    if not shutil.which('ffprobe'):
        print("Error: ffprobe is not installed or not in your PATH.")
        return

    # Collect audio files
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [Path(path)]
        else:
            print(f"'{path}' is not a supported audio file.")
            return
    elif os.path.isdir(path):
        audio_files = [file for ext in AUDIO_EXTENSIONS for file in Path(path).rglob(f"*{ext}")]
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        print(f"'{path}' is not a file or directory.")
        return

    total_files = len(audio_files)
    if show_progress:
        print_progress_bar(0, total_files, "Analyzing audio")

    for index, audio_file in enumerate(audio_files):
        output_stream.write(f"Analyzing: {audio_file}\n")
        try:
            # Run ffprobe to get metadata in JSON format
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(audio_file)]
            result = subprocess.check_output(cmd, universal_newlines=True)
            data = json.loads(result)
            stream = data["streams"][0]  # Assume first stream is audio

            # Extract metadata with defaults for missing values
            codec = stream.get("codec_name", "N/A")
            sample_rate = stream.get("sample_rate", "N/A")
            channels = stream.get("channels", "N/A")
            bit_depth = stream.get("bits_per_raw_sample", "N/A")
            bit_rate = data["format"].get("bit_rate", "N/A")

            # Format channel info for readability
            if channels == "N/A":
                channel_info = "N/A"
            elif channels == 1:
                channel_info = "Mono"
            elif channels == 2:
                channel_info = "Stereo"
            else:
                channel_info = f"{channels} channels"

            # Write basic metadata
            output_stream.write(f"  Bitrate: {bit_rate} bps\n" if bit_rate != "N/A" else "  Bitrate: N/A\n")
            output_stream.write(f"  Sample Rate: {sample_rate} Hz\n" if sample_rate != "N/A" else "  Sample Rate: N/A\n")
            output_stream.write(f"  Bit Depth: {bit_depth} bits\n" if bit_depth != "N/A" else "  Bit Depth: N/A\n")
            output_stream.write(f"  Channels: {channel_info}\n")
            output_stream.write(f"  Codec: {codec}\n")

            # Add codec-specific info
            if audio_file.suffix.lower() == ".m4a":
                if "aac" in codec.lower():
                    output_stream.write("  [INFO] AAC (lossy) codec detected.\n")
                elif "alac" in codec.lower():
                    output_stream.write("  [INFO] ALAC (lossless) codec detected.\n")
                else:
                    output_stream.write(f"  [WARNING] Unknown codec: {codec}\n")
            elif audio_file.suffix.lower() in [".opus", ".mp3"]:
                output_stream.write(f"  [INFO] Lossy codec: {codec}\n")

            # Check for quality warnings
            if bit_depth != "N/A" and int(bit_depth) < 16:
                output_stream.write("  [WARNING] Low bit depth may indicate lossy encoding.\n")
            if sample_rate != "N/A" and int(sample_rate) < 44100:
                output_stream.write("  [WARNING] Low sample rate may indicate lossy encoding.\n")

            output_stream.write("\n")
        except Exception as e:
            output_stream.write(f"  [ERROR] Failed to analyze: {e}\n")

        if show_progress:
            print_progress_bar(index + 1, total_files, "Analyzing audio")

def main():
    """Sets up command-line interface and runs subcommands."""
    parser = argparse.ArgumentParser(description="Tool for managing audio files")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Setup 'check' command
    check_parser = subparsers.add_parser("check", help="Verify audio file integrity")
    check_parser.add_argument("path", type=path_type, help="File or directory to check")
    check_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")
    check_parser.add_argument("--save-log", action="store_true", help="Save results to a log file")

    # Setup 'cover-art' command
    cover_parser = subparsers.add_parser("cover-art", help="Hide or show cover art files")
    cover_group = cover_parser.add_mutually_exclusive_group(required=True)
    cover_group.add_argument("--hide", action="store_true", help="Hide cover art by adding a dot prefix")
    cover_group.add_argument("--show", action="store_true", help="Show cover art by removing dot prefix")
    cover_parser.add_argument("path", type=directory_path, help="Directory to process")

    # Setup 'info' command
    info_parser = subparsers.add_parser("info", help="Analyze audio file metadata")
    info_parser.add_argument("path", type=path_type, help="File or directory to analyze")
    info_parser.add_argument("-o", "--output", default="audio_analysis.txt", help="Output file for results")
    info_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")

    args = parser.parse_args()

    # Dispatch to appropriate subcommand
    if args.command == "check":
        check_integrity(args.path, verbose=args.verbose, save_log=args.save_log)
    elif args.command == "cover-art":
        process_cover_art(args.path, hide=args.hide)
    elif args.command == "info":
        if args.verbose:
            analyze_audio(args.path, sys.stdout, show_progress=False)
        else:
            output_file = args.output
            if output_file == "audio_analysis.txt":  # Add timestamp to default name
                output_file = f"audio_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
            with open(output_file, "w") as f:
                analyze_audio(args.path, f)
            print(f"Analysis complete. Results saved to '{output_file}'")

if __name__ == "__main__":
    """Entry point: Runs main() and handles Ctrl+C gracefully."""
    try:
        main()
    except KeyboardInterrupt:
        print("Quitting job...")  # User-friendly exit message
