import os
import sys
import json
import subprocess
import time
import requests
from urllib.parse import urlparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import colorama
from colorama import Fore, Back, Style
import tqdm
import random
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Initialize colorama for cross-platform colored output
colorama.init(autoreset=True)


def get_script_path():
    return os.path.dirname(os.path.realpath(__file__))


def get_paths():
    script_path = get_script_path()
    xray_path = os.path.join(
        script_path,
        r"xray.exe",
    )
    config_path = os.path.join(
        script_path,
        r"config.json",
    )
    # complete
    ipadd_path = os.path.join(
        script_path,
        r"ipad.txt",
    )
    log_file = os.path.join(script_path, "pings.txt")
    xray_log_file = os.path.join(script_path, "xraylogs.txt")
    download_log_file = os.path.join(script_path, "download_speeds.txt")
    plots_dir = os.path.join(script_path, "plots")
    return xray_path, config_path, log_file, xray_log_file, download_log_file, plots_dir


def check_file_exists(file_path):
    return os.path.exists(file_path)


def create_file_if_not_exists(file_path):
    if not check_file_exists(file_path):
        open(file_path, "w").close()


def create_directory_if_not_exists(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def clear_file_content(file_path):
    open(file_path, "w").close()


def get_user_input(prompt, default_value):
    print(f"{Fore.CYAN}{prompt}{Style.RESET_ALL}")
    user_input = input(
        f"{Fore.YELLOW}Enter value (or press Enter for {default_value}): {Style.RESET_ALL}"
    )
    return int(user_input) if user_input else default_value


def print_banner():
    """Print a beautiful banner for the application"""
    banner = f"""
{Fore.MAGENTA}╔══════════════════════════════════════════════════════════════════════════════╗
║                    {Fore.CYAN}🚀 VPN Fragment Testing Tool v2.1 🚀{Fore.MAGENTA}                    ║
║                                                                              ║
║  {Fore.GREEN}• Random fragmentation configuration testing{Fore.MAGENTA}                          ║
║  {Fore.GREEN}• Latency and download speed optimization{Fore.MAGENTA}                              ║
║  {Fore.GREEN}• Real-time progress tracking with plots{Fore.MAGENTA}                               ║
║  {Fore.GREEN}• Comprehensive performance analysis{Fore.MAGENTA}                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def print_section_header(title):
    """Print a formatted section header"""
    print(f"\n{Fore.BLUE}{'='*80}")
    print(f"{Fore.WHITE}{title:^80}")
    print(f"{Fore.BLUE}{'='*80}{Style.RESET_ALL}\n")


def get_random_combination(
    address_options, packets_options, length_options, interval_options
):
    address = random.choice(address_options)
    packets = random.choice(packets_options)
    length = random.choice(length_options)
    interval = random.choice(interval_options)
    return address, packets, length, interval


def get_unique_random_combination(
    used_combinations,
    address_options,
    packets_options,
    length_options,
    interval_options,
    max_attempts=100,
):
    for _ in range(max_attempts):
        address, packets, length, interval = get_random_combination(
            address_options, packets_options, length_options, interval_options
        )
        combination = f"{address},{packets},{length},{interval}"
        if combination not in used_combinations:
            used_combinations.add(combination)
            return address, packets, length, interval
    return None, None, None, None


def get_unique_combination(
    used_combinations, packets_options, length_options, interval_options
):
    for packets in packets_options:
        for length in length_options:
            for interval in interval_options:
                combination = f"{packets},{length},{interval}"
                if combination not in used_combinations:
                    used_combinations.add(combination)
                    return packets, length, interval
    return None, None, None  # Return None values when no more combinations available


def modify_config(config_path, address, packets, length, interval):
    with open(config_path, "r") as file:
        config = json.load(file)

    # Set fragmentation parameters in the 'fragment' outbound
    fragment_outbound = next(
        (outbound for outbound in config["outbounds"] if outbound["tag"] == "fragment"),
        None,
    )
    if fragment_outbound:
        fragment_outbound["settings"]["fragment"]["packets"] = packets
        fragment_outbound["settings"]["fragment"]["length"] = length
        fragment_outbound["settings"]["fragment"]["interval"] = interval
    else:
        print(f"{Fore.RED}No 'fragment' outbound found in config.json{Style.RESET_ALL}")
        return

    # Set address in the 'proxy' outbound (vnext[0].address)
    proxy_outbound = next(
        (outbound for outbound in config["outbounds"] if outbound["tag"] == "proxy"),
        None,
    )
    if proxy_outbound:
        try:
            proxy_outbound["settings"]["vnext"][0]["address"] = address
        except Exception as e:
            print(
                f"{Fore.RED}Failed to set address in proxy outbound: {e}{Style.RESET_ALL}"
            )
    else:
        print(f"{Fore.RED}No 'proxy' outbound found in config.json{Style.RESET_ALL}")

    with open(config_path, "w") as file:
        json.dump(config, file, indent=4)


def stop_xray_process():
    try:
        subprocess.run(
            ["powershell", "-Command", 'Stop-Process -Name "xray" -Force'],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        pass


def send_http_request_optimized(
    ping_count, timeout, http_proxy_server, http_proxy_port, log_file
):
    """Optimized HTTP request function with better error handling"""
    url = "http://cp.cloudflare.com"
    individual_times = []

    proxies = {
        "http": f"http://{http_proxy_server}:{http_proxy_port}",
        "https": f"http://{http_proxy_server}:{http_proxy_port}",
    }

    for i in range(ping_count):
        start_time = time.time()
        try:
            response = requests.get(url, proxies=proxies, timeout=timeout)
            response.raise_for_status()
            elapsed_time = (time.time() - start_time) * 1000
            individual_times.append(elapsed_time)
        except Exception:
            individual_times.append(-1)

        if i < ping_count - 1:  # Don't sleep after the last request
            time.sleep(0.5)  # Reduced sleep time for faster testing

    individual_times = individual_times[1:]  # Skip first request
    valid_pings = [t for t in individual_times if t != -1]

    if valid_pings:
        average_ping = sum(valid_pings) / len(valid_pings)
    else:
        average_ping = 0

    with open(log_file, "a") as file:
        file.write(f"Individual Ping Times: {','.join(map(str, individual_times))}\n")

    return average_ping


def test_download_speed_optimized(
    http_proxy_server, http_proxy_port, timeout_sec, log_file, max_retries=2
):
    """
    Optimized download speed testing with better error handling and faster testing
    """
    test_urls = [
        "https://speed.cloudflare.com/__down?bytes=2097152",  # 2MB file (faster)
        "https://httpbin.org/bytes/1048576",  # 1MB file (backup)
    ]
    proxies = {
        "http": f"http://{http_proxy_server}:{http_proxy_port}",
        "https": f"http://{http_proxy_server}:{http_proxy_port}",
    }
    best_speed = 0
    for url in test_urls:
        for attempt in range(1, max_retries + 1):
            try:
                start_time = time.time()
                response = requests.get(
                    url, proxies=proxies, timeout=timeout_sec, stream=True
                )
                response.raise_for_status()
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        total_bytes += len(chunk)
                end_time = time.time()
                download_time = end_time - start_time
                if download_time > 0 and total_bytes > 0:
                    speed_mbps = (total_bytes * 8) / (1024 * 1024 * download_time)
                    best_speed = max(best_speed, speed_mbps)
                    with open(log_file, "a") as file:
                        file.write(
                            f"Download test: {total_bytes} bytes in {download_time:.2f}s = {speed_mbps:.2f} Mbps\n"
                        )
                    return best_speed
            except Exception as e:
                with open(log_file, "a") as file:
                    file.write(
                        f"Download test failed for {url} (attempt {attempt}): {str(e)}\n"
                    )
                if attempt == max_retries:
                    continue  # Try next URL
    return best_speed


def create_performance_plots(all_results, download_results, plots_dir):
    """Create comprehensive performance plots"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Set up the plotting style
    plt.style.use("default")
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(
        f"VPN Fragment Performance Analysis - {timestamp}",
        fontsize=16,
        fontweight="bold",
    )

    # Extract data for plotting
    instances = [r["Instance"] for r in all_results]
    pings = [r["AverageResponseTime"] for r in all_results]
    packets = [r["Packets"] for r in all_results]
    lengths = [r["Length"] for r in all_results]
    intervals = [r["Interval"] for r in all_results]

    # 1. Ping Time vs Instance
    ax1 = axes[0, 0]
    colors = ["green" if p < 100 else "orange" if p < 200 else "red" for p in pings]
    bars1 = ax1.bar(instances, pings, color=colors, alpha=0.7)
    ax1.set_xlabel("Instance Number")
    ax1.set_ylabel("Ping Time (ms)")
    ax1.set_title("Ping Time by Instance")
    ax1.grid(True, alpha=0.3)

    # Add value labels on bars
    for bar, ping in zip(bars1, pings):
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 1,
            f"{ping:.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # 2. Ping Time Distribution
    ax2 = axes[0, 1]
    ax2.hist(pings, bins=10, color="skyblue", alpha=0.7, edgecolor="black")
    ax2.set_xlabel("Ping Time (ms)")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Ping Time Distribution")
    ax2.grid(True, alpha=0.3)

    # 3. Parameter Performance Analysis
    ax3 = axes[1, 0]
    # Group by packets and calculate average ping
    packet_groups = {}
    for i, packet in enumerate(packets):
        if packet not in packet_groups:
            packet_groups[packet] = []
        packet_groups[packet].append(pings[i])

    packet_avgs = {k: np.mean(v) for k, v in packet_groups.items()}
    ax3.bar(packet_avgs.keys(), packet_avgs.values(), color="lightcoral", alpha=0.7)
    ax3.set_xlabel("Packet Configuration")
    ax3.set_ylabel("Average Ping Time (ms)")
    ax3.set_title("Average Ping by Packet Configuration")
    ax3.grid(True, alpha=0.3)

    # 4. Top 3 Configurations with Download Speed
    ax4 = axes[1, 1]
    if download_results:
        top_ranks = [r["Rank"] for r in download_results]
        top_pings = [r["AverageResponseTime"] for r in download_results]
        top_speeds = [r["DownloadSpeed"] for r in download_results]

        x = np.arange(len(top_ranks))
        width = 0.35

        bars1 = ax4.bar(
            x - width / 2,
            top_pings,
            width,
            label="Ping (ms)",
            color="lightblue",
            alpha=0.7,
        )
        ax4_twin = ax4.twinx()
        bars2 = ax4_twin.bar(
            x + width / 2,
            top_speeds,
            width,
            label="Download (Mbps)",
            color="lightgreen",
            alpha=0.7,
        )

        ax4.set_xlabel("Rank")
        ax4.set_ylabel("Ping Time (ms)", color="blue")
        ax4_twin.set_ylabel("Download Speed (Mbps)", color="green")
        ax4.set_title("Top 3 Configurations: Ping vs Download Speed")
        ax4.set_xticks(x)
        ax4.set_xticklabels([f"#{r}" for r in top_ranks])
        ax4.grid(True, alpha=0.3)

        # Add legends
        ax4.legend(loc="upper left")
        ax4_twin.legend(loc="upper right")

    plt.tight_layout()

    # Save the plot
    plot_filename = os.path.join(plots_dir, f"performance_analysis_{timestamp}.png")
    plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
    plt.close()

    return plot_filename


def create_scatter_plot(all_results, plots_dir):
    """Create a scatter plot showing parameter relationships"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Extract data
    pings = [r["AverageResponseTime"] for r in all_results]
    lengths_numeric = []
    intervals_numeric = []

    # Convert length and interval to numeric values for plotting
    for result in all_results:
        # Extract first number from length (e.g., "10-20" -> 10)
        length_val = int(result["Length"].split("-")[0])
        lengths_numeric.append(length_val)

        # Extract first number from interval (e.g., "5-10" -> 5)
        interval_val = int(result["Interval"].split("-")[0])
        intervals_numeric.append(interval_val)

    # Create scatter plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle(
        f"Parameter Relationship Analysis - {timestamp}", fontsize=16, fontweight="bold"
    )

    # Scatter plot: Length vs Ping
    scatter1 = ax1.scatter(
        lengths_numeric, pings, c=pings, cmap="viridis", alpha=0.7, s=100
    )
    ax1.set_xlabel("Length (first value)")
    ax1.set_ylabel("Ping Time (ms)")
    ax1.set_title("Length vs Ping Time")
    ax1.grid(True, alpha=0.3)
    plt.colorbar(scatter1, ax=ax1, label="Ping Time (ms)")

    # Scatter plot: Interval vs Ping
    scatter2 = ax2.scatter(
        intervals_numeric, pings, c=pings, cmap="plasma", alpha=0.7, s=100
    )
    ax2.set_xlabel("Interval (first value)")
    ax2.set_ylabel("Ping Time (ms)")
    ax2.set_title("Interval vs Ping Time")
    ax2.grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=ax2, label="Ping Time (ms)")

    plt.tight_layout()

    # Save the plot
    plot_filename = os.path.join(plots_dir, f"parameter_analysis_{timestamp}.png")
    plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
    plt.close()

    return plot_filename


def print_results_table(results, title="Test Results"):
    """Print a beautiful formatted results table"""
    print_section_header(title)
    # Table header
    header = f"{Fore.CYAN}{'Instance':<10} {'Address':<22} {'Packets':<12} {'Length':<12} {'Interval':<12} {'Ping (ms)':<12}{Style.RESET_ALL}"
    print(header)
    print(f"{Fore.CYAN}{'-' * 100}{Style.RESET_ALL}")
    # Table rows
    for result in results:
        ping_color = (
            Fore.GREEN
            if result["AverageResponseTime"] < 100
            else Fore.YELLOW if result["AverageResponseTime"] < 200 else Fore.RED
        )
        print(
            f"{result['Instance']:<10} {str(result.get('Address', '-')):<22} {result['Packets']:<12} {result['Length']:<12} {result['Interval']:<12} {ping_color}{result['AverageResponseTime']:<12.2f}{Style.RESET_ALL}"
        )


def print_final_results_table(results):
    """Print the final comprehensive results table"""
    print_section_header("FINAL RESULTS - TOP CONFIGURATIONS")
    # Table header
    header = f"{Fore.CYAN}{'Rank':<5} {'Instance':<10} {'Address':<22} {'Packets':<12} {'Length':<12} {'Interval':<12} {'Ping (ms)':<12} {'Download (Mbps)':<15}{Style.RESET_ALL}"
    print(header)
    print(f"{Fore.CYAN}{'-' * 120}{Style.RESET_ALL}")
    # Table rows with color coding
    for result in results:
        ping_color = (
            Fore.GREEN
            if result["AverageResponseTime"] < 100
            else Fore.YELLOW if result["AverageResponseTime"] < 200 else Fore.RED
        )
        speed_color = (
            Fore.GREEN
            if result["DownloadSpeed"] > 10
            else Fore.YELLOW if result["DownloadSpeed"] > 5 else Fore.RED
        )
        print(
            f"{Fore.WHITE}{result['Rank']:<5} {result['Instance']:<10} {str(result.get('Address', '-')):<22} {result['Packets']:<12} {result['Length']:<12} "
            f"{result['Interval']:<12} {ping_color}{result['AverageResponseTime']:<12.2f}{Style.RESET_ALL} {speed_color}{result['DownloadSpeed']:<15.2f}{Style.RESET_ALL}"
        )


def main():
    print_banner()

    xray_path, config_path, log_file, xray_log_file, download_log_file, plots_dir = (
        get_paths()
    )

    if not check_file_exists(xray_path):
        print(f"{Fore.RED}❌ Error: xray.exe not found at {xray_path}{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.GREEN}✅ Xray executable found{Style.RESET_ALL}")

    create_file_if_not_exists(log_file)
    create_file_if_not_exists(xray_log_file)
    create_file_if_not_exists(download_log_file)
    create_directory_if_not_exists(plots_dir)
    clear_file_content(log_file)
    clear_file_content(xray_log_file)
    clear_file_content(download_log_file)

    print_section_header("CONFIGURATION SETUP")

    instances = get_user_input("Enter the number of instances to test", 10)
    timeout_sec = get_user_input("Enter the timeout for each ping test in seconds", 3)
    http_proxy_port = get_user_input("Enter the HTTP Listening port", 10809)
    ping_count = get_user_input("Enter the number of requests per instance", 3) + 1

    # Address options
    address_options = [
        "www.speedtest.net",
        # "www.tgju.org",
        # "www.azaronline.com",
        # "104.18.71.193",
    ]
    packets_options = ["1-1", "tlshello", "3-5"]  # "tlshello", "1-2", "1-3", "1-5"]
    length_options = [
        # "1-1",
        # "1-2",
        "1-3",
        # "2-5",
        # "1-5",
        # "1-10",
        # "3-5",
        # "5-10",
        # "3-10",
        # "10-15",
        # "10-30",
        "10-20",
        "40-50",
        # "50-100",
        # "100-150",
        # "100-200",
    ]
    interval_options = [
        "1-1",
        # "1-2",
        "3-5",
        # "1-5",
        "5-10",
        # "10-15",
        # "10-20",
        # "20-30",
        # "20-50",
        # "40-50",
        # "50-100",
        # "50-80",
        # "100-150",
        # "150-200",
        # "100-200",
    ]

    # Download speed test strategy
    print(f"{Fore.CYAN}Choose download speed testing strategy:{Style.RESET_ALL}")
    print(
        f"{Fore.GREEN}→{Style.RESET_ALL} 1. Test download speed for TOP 3 best ping instances only (faster)"
    )
    print(f"  2. Test download speed for ALL instances (comprehensive but slower)")
    while True:
        try:
            choice = input(
                f"{Fore.YELLOW}Enter your choice (1-2) or press Enter for default (1): {Style.RESET_ALL}"
            )
            if not choice:
                download_strategy = 0
                break
            choice_num = int(choice)
            if choice_num in [1, 2]:
                download_strategy = choice_num - 1
                break
            else:
                print(f"{Fore.RED}Please enter 1 or 2{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number{Style.RESET_ALL}")
    test_all_downloads = download_strategy == 1
    download_options = [
        "Test download speed for TOP 3 best ping instances only (faster)",
        "Test download speed for ALL instances (comprehensive but slower)",
    ]
    print(
        f"\n{Fore.GREEN}📊 Download speed testing: {download_options[download_strategy]}{Style.RESET_ALL}"
    )

    http_proxy_server = "127.0.0.1"
    all_results = []
    used_combinations = set()

    print_section_header("RANDOM LATENCY TESTING PHASE")

    print(
        f"{Fore.YELLOW}Testing {instances} random fragmentation configurations...{Style.RESET_ALL}\n"
    )

    with tqdm.tqdm(
        total=instances,
        desc="Testing Random Configurations",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
    ) as pbar:
        for i in range(instances):
            address, packets, length, interval = get_unique_random_combination(
                used_combinations,
                address_options,
                packets_options,
                length_options,
                interval_options,
            )
            if packets is None:
                print(
                    f"\n{Fore.YELLOW}⚠️  No more unique combinations available. Stopping at instance {i}.{Style.RESET_ALL}"
                )
                break
            pbar.set_description(
                f"Testing: addr:{address} p:{packets}/l:{length}/i:{interval}"
            )
            modify_config(config_path, address, packets, length, interval)
            stop_xray_process()
            subprocess.Popen(
                [xray_path, "-c", config_path],
                stdout=open(xray_log_file, "w"),
                stderr=open(f"{xray_log_file}.Error", "w"),
            )
            time.sleep(2)
            with open(log_file, "a") as file:
                file.write(
                    f"Testing with address={address}, packets={packets}, length={length}, interval={interval}...\n"
                )
            average_ping = send_http_request_optimized(
                ping_count, timeout_sec, http_proxy_server, http_proxy_port, log_file
            )
            with open(log_file, "a") as file:
                file.write(f"Average Ping Time: {average_ping} ms\n")
            # Print result immediately
            print(
                f"{Fore.CYAN}Instance {i+1}: address={address}, packets={packets}, length={length}, interval={interval} | Ping: {average_ping:.2f} ms",
                end="",
            )
            result_entry = {
                "Instance": i + 1,
                "Address": address,
                "Packets": packets,
                "Length": length,
                "Interval": interval,
                "AverageResponseTime": average_ping,
            }
            # If testing all, do download speed now
            if test_all_downloads:
                download_speed = test_download_speed_optimized(
                    http_proxy_server, http_proxy_port, timeout_sec, download_log_file
                )
                result_entry["DownloadSpeed"] = download_speed
                print(f" | Download: {download_speed:.2f} Mbps{Style.RESET_ALL}")
            else:
                print(f"{Style.RESET_ALL}")
            all_results.append(result_entry)
            pbar.update(1)
            time.sleep(0.5)

    # Display all results
    print_results_table(all_results, "ALL TEST RESULTS")

    # Get top 3 for download speed testing
    valid_results = [entry for entry in all_results if entry["AverageResponseTime"] > 0]
    if test_all_downloads:
        download_test_instances = valid_results
        print_results_table(
            download_test_instances, "DOWNLOAD SPEED TESTING - ALL INSTANCES"
        )
    else:
        download_test_instances = sorted(
            valid_results, key=lambda x: x["AverageResponseTime"]
        )[:3]
        print_results_table(
            download_test_instances, "DOWNLOAD SPEED TESTING - TOP 3 LOWEST LATENCY"
        )

    # Download speed testing phase
    print_section_header("DOWNLOAD SPEED TESTING PHASE")

    download_results = []

    with tqdm.tqdm(
        total=len(download_test_instances),
        desc="Testing Download Speeds",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
    ) as pbar:

        for i, entry in enumerate(download_test_instances):
            pbar.set_description(
                f"Testing config {i+1}: addr:{entry['Address']} p:{entry['Packets']}/l:{entry['Length']}/i:{entry['Interval']}"
            )

            # Apply the configuration
            modify_config(
                config_path,
                entry["Address"],
                entry["Packets"],
                entry["Length"],
                entry["Interval"],
            )
            stop_xray_process()

            # Start xray with this configuration
            subprocess.Popen(
                [xray_path, "-c", config_path],
                stdout=open(xray_log_file, "w"),
                stderr=open(f"{xray_log_file}.Error", "w"),
            )
            time.sleep(2)

            # Test download speed
            download_speed = test_download_speed_optimized(
                http_proxy_server, http_proxy_port, timeout_sec, download_log_file
            )

            download_results.append(
                {
                    "Rank": i + 1,
                    "Instance": entry["Instance"],
                    "Address": entry["Address"],
                    "Packets": entry["Packets"],
                    "Length": entry["Length"],
                    "Interval": entry["Interval"],
                    "AverageResponseTime": entry["AverageResponseTime"],
                    "DownloadSpeed": download_speed,
                }
            )

            # Print result immediately
            print(
                f"{Fore.CYAN}Instance {entry['Instance']}: address={entry['Address']}, packets={entry['Packets']}, length={entry['Length']}, interval={entry['Interval']} | Ping: {entry['AverageResponseTime']:.2f} ms | Download: {download_speed:.2f} Mbps{Style.RESET_ALL}"
            )

            pbar.update(1)

            # Stop xray before testing next configuration
            stop_xray_process()
            time.sleep(0.5)

    # Display final comprehensive results
    print_final_results_table(download_results)

    # Create plots
    print_section_header("GENERATING PERFORMANCE PLOTS")

    try:
        print(f"{Fore.YELLOW}Creating performance analysis plots...{Style.RESET_ALL}")

        # Create main performance plots
        main_plot = create_performance_plots(all_results, download_results, plots_dir)
        print(
            f"{Fore.GREEN}✅ Main performance plot saved: {os.path.basename(main_plot)}{Style.RESET_ALL}"
        )

        # Create parameter analysis plots
        param_plot = create_scatter_plot(all_results, plots_dir)
        print(
            f"{Fore.GREEN}✅ Parameter analysis plot saved: {os.path.basename(param_plot)}{Style.RESET_ALL}"
        )

        print(f"{Fore.GREEN}📊 All plots saved to: {plots_dir}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}❌ Error creating plots: {str(e)}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}Make sure matplotlib is installed: pip install matplotlib{Style.RESET_ALL}"
        )

    # Save comprehensive results to file
    with open(download_log_file, "a") as file:
        file.write("\n" + "=" * 100 + "\n")
        file.write("FINAL RESULTS - TOP 3 CONFIGURATIONS WITH DOWNLOAD SPEEDS\n")
        file.write("=" * 100 + "\n")
        file.write(
            f"{'Rank':<5} {'Instance':<10} {'Packets':<15} {'Length':<15} {'Interval':<15} {'Ping (ms)':<12} {'Download (Mbps)':<15}\n"
        )
        file.write("-" * 100 + "\n")

        for result in download_results:
            file.write(
                f"{result['Rank']:<5} {result['Instance']:<10} {result['Packets']:<15} {result['Length']:<15} "
                f"{result['Interval']:<15} {result['AverageResponseTime']:<12.2f} {result['DownloadSpeed']:<15.2f}\n"
            )

    print(f"\n{Fore.GREEN}✅ Results saved to: {download_log_file}{Style.RESET_ALL}")

    # Find best overall configuration
    if download_results:
        best_overall = min(download_results, key=lambda x: x["AverageResponseTime"])
        print(f"\n{Fore.GREEN}🏆 Best Overall Configuration:{Style.RESET_ALL}")
        print(f"   Packets: {best_overall['Packets']}")
        print(f"   Length: {best_overall['Length']}")
        print(f"   Interval: {best_overall['Interval']}")
        print(f"   Ping: {best_overall['AverageResponseTime']:.2f} ms")
        print(f"   Download Speed: {best_overall['DownloadSpeed']:.2f} Mbps")

    stop_xray_process()
    print(f"\n{Fore.GREEN}🎉 Testing completed successfully!{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
