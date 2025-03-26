"""
Benchmark script for parallel fact extraction performance.

This script tests different parallelism levels to determine the optimal
number of concurrent workers for your system.
"""

import os
import asyncio
import time
import argparse
import logging
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Dict, List, Any

from src.graph.nodes import process_document
from src import ProcessingState
from src.config import src.config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("benchmark.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def benchmark_parallelism(file_path: str, concurrency_levels: List[int]) -> Dict[int, Dict[str, Any]]:
    """
    Benchmark different concurrency levels for fact extraction.
    
    Args:
        file_path: Path to the document to process
        concurrency_levels: List of concurrency levels to test
        
    Returns:
        Dictionary mapping concurrency levels to performance metrics
    """
    results = {}
    
    for level in concurrency_levels:
        logger.info(f"Testing concurrency level: {level}")
        
        # Reset repositories to ensure fair comparison
        # This deletes existing Excel files so each test starts from the same state
        for file_path in [
            config["chunks_excel_path"], 
            config["facts_excel_path"], 
            config["rejected_facts_excel_path"]
        ]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Removed {file_path} for clean test")
                except Exception as e:
                    logger.error(f"Failed to remove {file_path}: {e}")
        
        # Create fresh state
        state = ProcessingState()
        
        # Measure processing time
        start_time = time.time()
        
        try:
            # Process document with current concurrency level
            result = await process_document(file_path, state, max_concurrent_chunks=level)
            
            # Record metrics
            processing_time = time.time() - start_time
            
            results[level] = {
                "time": processing_time,
                "chunks_processed": result.get("chunks_processed", 0),
                "facts_extracted": result.get("facts_extracted", 0),
                "verified_facts": result.get("verified_facts", 0),
                "rejected_facts": result.get("rejected_facts", 0),
                "errors": result.get("errors", [])
            }
            
            logger.info(f"Concurrency level {level} completed in {processing_time:.2f} seconds")
            logger.info(f"Results: {results[level]}")
            
            # Add a delay between tests to allow system to recover
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error benchmarking concurrency level {level}: {e}")
            results[level] = {
                "time": -1,
                "error": str(e)
            }
    
    return results

def plot_results(results: Dict[int, Dict[str, Any]], output_file: str = None) -> None:
    """
    Plot benchmark results.
    
    Args:
        results: Dictionary mapping concurrency levels to performance metrics
        output_file: Optional path to save the plot image
    """
    # Extract concurrency levels and times
    levels = []
    times = []
    facts = []
    
    for level, data in sorted(results.items()):
        if data.get("time", -1) > 0:
            levels.append(level)
            times.append(data["time"])
            facts.append(data.get("verified_facts", 0))
    
    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # Plot processing time
    color = 'tab:blue'
    ax1.set_xlabel('Concurrency Level')
    ax1.set_ylabel('Processing Time (seconds)', color=color)
    line1 = ax1.plot(levels, times, 'o-', color=color, label='Processing Time')
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Add second y-axis for facts count
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Verified Facts Count', color=color)
    line2 = ax2.plot(levels, facts, 's--', color=color, label='Verified Facts')
    ax2.tick_params(axis='y', labelcolor=color)
    
    # Title and grid
    plt.title('Fact Extraction Performance by Concurrency Level')
    ax1.grid(True, alpha=0.3)
    
    # Combine legends
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper center')
    
    # Annotate optimal level
    if times:
        min_time_idx = times.index(min(times))
        optimal_level = levels[min_time_idx]
        
        plt.annotate(f'Optimal Level: {optimal_level}',
                    xy=(optimal_level, times[min_time_idx]),
                    xytext=(optimal_level, times[min_time_idx]*1.2),
                    arrowprops=dict(facecolor='black', shrink=0.05, width=1.5),
                    horizontalalignment='center')
    
    # Add speedup table
    if times and len(times) > 1:
        table_data = []
        base_time = times[0]  # Time for single thread
        
        for i, level in enumerate(levels):
            speedup = base_time / times[i]
            efficiency = speedup / level
            table_data.append([level, f"{speedup:.2f}x", f"{efficiency:.2f}"])
        
        plt.table(cellText=table_data,
                colLabels=['Concurrency', 'Speedup', 'Efficiency'],
                colWidths=[0.1, 0.1, 0.1],
                loc='lower right')
    
    plt.tight_layout()
    
    # Save if output file specified
    if output_file:
        plt.savefig(output_file)
        logger.info(f"Plot saved to {output_file}")
    
    plt.show()

async def main():
    """Run the benchmark."""
    parser = argparse.ArgumentParser(description='Benchmark parallel fact extraction performance')
    parser.add_argument('file', help='Path to the document to process')
    parser.add_argument('--levels', type=int, nargs='+', default=[1, 2, 4, 8, 16],
                        help='Concurrency levels to test (default: 1, 2, 4, 8, 16)')
    parser.add_argument('--output', default=None, help='Path to save benchmark results plot')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        return
    
    # Run benchmark
    logger.info(f"Starting benchmark with document: {args.file}")
    logger.info(f"Testing concurrency levels: {args.levels}")
    
    results = await benchmark_parallelism(args.file, args.levels)
    
    # Print results
    logger.info("\nBenchmark Results:")
    logger.info("-" * 50)
    
    # Find the fastest level
    fastest_level = None
    fastest_time = float('inf')
    
    for level, data in sorted(results.items()):
        time_taken = data.get("time", -1)
        if time_taken > 0:
            logger.info(f"Concurrency Level {level}: {time_taken:.2f} seconds")
            
            # Track fastest level
            if time_taken < fastest_time:
                fastest_time = time_taken
                fastest_level = level
    
    # Recommend optimal level
    if fastest_level is not None:
        logger.info("-" * 50)
        logger.info(f"Recommended concurrency level: {fastest_level}")
        
        # Calculate speedup compared to sequential processing
        if 1 in results and results[1]["time"] > 0:
            speedup = results[1]["time"] / results[fastest_level]["time"]
            logger.info(f"Speedup over sequential processing: {speedup:.2f}x")
    
    # Generate plot
    output_file = args.output
    if output_file is None:
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"benchmark_results_{timestamp}.png"
    
    plot_results(results, output_file)

if __name__ == "__main__":
    asyncio.run(main()) 