#!/usr/bin/env python3
"""
Batch Model Swap - Process multiple PDP folders in parallel.

This script wraps model_swap.py to process multiple PDP folders concurrently,
with a configurable parallelism level (default: 3, max: 5).

Each parallel worker runs a full independent workflow (auth, upload, job, download)
so there is no shared state between threads.

Usage:
    # Process all subfolders in a directory
    python batch_swap.py \
        --input-dir PDP/ \
        --token YOUR_API_TOKEN \
        --identity-code PiktidPremium \
        --output-dir results/

    # Process specific folders
    python batch_swap.py \
        --input-folders PDP/ARTICLE1 PDP/ARTICLE2 PDP/ARTICLE3 \
        --token YOUR_API_TOKEN \
        --identity-image identities/female/Lisa.jpg \
        --output-dir results/ \
        --parallel 5
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from model_swap import ModelSwap


def process_single_pdp(base_url, token, input_folder, identity_code,
                       identity_image, output_folder, post_process, model,
                       use_anchor=False):
    """Process a single PDP folder. Runs in its own thread with its own ModelSwap instance."""
    start = time.time()

    processor = ModelSwap(
        base_url=base_url,
        token=token,
        input_folder=str(input_folder),
        identity_code=identity_code,
        identity_image=identity_image,
        output_folder=str(output_folder),
        post_process=post_process,
        model=model,
        use_anchor=use_anchor,
    )

    success = processor.run()
    elapsed = time.time() - start

    return {
        "folder": input_folder.name,
        "success": success,
        "processing_time": round(elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Batch Model Swap - Process multiple PDP folders in parallel"
    )

    # Input: either --input-dir (all subfolders) or --input-folders (specific paths)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-dir",
        type=str,
        help="Directory containing PDP subfolders (each subfolder is processed as a separate job)",
    )
    input_group.add_argument(
        "--input-folders",
        type=str,
        nargs="+",
        help="Specific PDP folder paths to process",
    )

    parser.add_argument(
        "--token", type=str, required=True, help="API token from https://app.on-model.com/profile?tab=tokens"
    )
    parser.add_argument(
        "--identity-code", type=str, default=None, help="Existing identity code to use"
    )
    parser.add_argument(
        "--identity-image", type=str, default=None, help="Path to identity image file to upload"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Base output directory — results saved to <output-dir>/<folder-name>/ (default: output)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://v2.api.piktid.com",
        help="API base URL (default: https://v2.api.piktid.com)",
    )
    parser.add_argument(
        "--post-process", action="store_true", help="Enable post-processing (default: False)"
    )
    parser.add_argument(
        "--model",
        choices=["auto", "onda", "nano_banana_2"],
        default="auto",
        help="Generation engine. 'auto' (default) and 'nano_banana_2' both swap via "
             "Google's Nano Banana 2. Use 'onda' for PiktID's proprietary Onda engine, "
             "which preserves the original garment pixels more literally but runs slower.",
    )
    parser.add_argument(
        "--use-anchor",
        action="store_true",
        help="Keep the model looking like the same person across each folder's batch, "
             "with steadier skin tone from shot to shot. Ignored with --model onda. "
             "Off by default.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3, max: 5)",
    )

    args = parser.parse_args()

    if not args.identity_code and not args.identity_image:
        parser.error("Either --identity-code or --identity-image must be provided")

    # Cap parallelism at 5 to respect API rate limits
    parallel = max(1, min(args.parallel, 5))

    # Collect input folders
    if args.input_dir:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"Input directory not found: {input_dir}")
            exit(1)
        folders = sorted([f for f in input_dir.iterdir() if f.is_dir()])
    else:
        folders = [Path(f) for f in args.input_folders]
        missing = [f for f in folders if not f.exists()]
        if missing:
            for f in missing:
                print(f"Folder not found: {f}")
            exit(1)

    if not folders:
        print("No folders to process")
        exit(1)

    output_dir = Path(args.output_dir)

    print("=" * 70)
    print("Batch Model Swap")
    print("=" * 70)
    print(f"  Folders to process: {len(folders)}")
    print(f"  Parallel workers:   {parallel}")
    print(f"  Output directory:   {output_dir}")
    print(f"  Post-processing:    {args.post_process}")
    print(f"  Model:              {args.model}")
    print(f"  Consistency:        {'on' if args.use_anchor else 'off'}")
    print(f"  API base URL:       {args.base_url}")
    print("=" * 70)

    for i, folder in enumerate(folders, 1):
        print(f"  {i}. {folder.name}")
    print()

    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        future_to_folder = {}

        for folder in folders:
            per_folder_output = output_dir / folder.name
            future = executor.submit(
                process_single_pdp,
                args.base_url,
                args.token,
                folder,
                args.identity_code,
                args.identity_image,
                per_folder_output,
                args.post_process,
                args.model,
                args.use_anchor,
            )
            future_to_folder[future] = folder.name

        for future in as_completed(future_to_folder):
            folder_name = future_to_folder[future]
            try:
                result = future.result()
                results.append(result)
                status = "OK" if result["success"] else "FAILED"
                print(
                    f"\n[{len(results)}/{len(folders)}] {folder_name}: {status}"
                    f" ({result['processing_time']}s)"
                )
            except Exception as e:
                results.append({"folder": folder_name, "success": False, "error": str(e)})
                print(f"\n[{len(results)}/{len(folders)}] {folder_name}: ERROR - {e}")

    # Summary
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"\n{'=' * 70}")
    print("Summary")
    print(f"{'=' * 70}")
    print(f"  Total:      {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Failed:     {failed}")
    print(f"  Time:       {elapsed:.1f}s ({elapsed / 60:.1f} minutes)")

    if failed > 0:
        print(f"\n  Failed folders:")
        for r in results:
            if not r["success"]:
                error = r.get("error", "see console output above")
                print(f"    - {r['folder']}: {error}")

    print(f"{'=' * 70}")

    # Save batch summary
    summary_file = output_dir / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(summary_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "configuration": {
                    "parallel": parallel,
                    "post_process": args.post_process,
                    "model": args.model,
                    "use_anchor": args.use_anchor,
                    "base_url": args.base_url,
                    "identity_code": args.identity_code,
                    "identity_image": args.identity_image,
                },
                "total_folders": len(results),
                "successful": successful,
                "failed": failed,
                "total_time_seconds": round(elapsed, 1),
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"Batch summary saved to {summary_file}")

    if failed > 0:
        exit(1)


if __name__ == "__main__":
    main()
