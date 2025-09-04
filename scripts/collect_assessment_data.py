#!/usr/bin/env python3
"""
Kubernetes Cluster Assessment Data Collection Script

This script deploys sick/healthy cluster configurations to minikube,
runs assessment commands, and saves the output for LLM training data.
"""

import subprocess
import time
import os
import json
from datetime import datetime
from pathlib import Path
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ClusterAssessmentCollector:
    def __init__(self, cluster_id, output_dir="assessment_data"):
        self.cluster_id = cluster_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Assessment commands to run
        self.assessment_commands = [
            {
                "name": "cluster-info",
                "command": ["kubectl", "cluster-info"],
                "description": "Basic cluster information",
            },
            {
                "name": "get_nodes_-o_wide",
                "command": ["kubectl", "get", "nodes", "-o", "wide"],
                "description": "Node status and details",
            },
            {
                "name": "get_pods_--all-namespaces_--field-selector=status.phase!=Running",
                "command": [
                    "kubectl",
                    "get",
                    "pods",
                    "--all-namespaces",
                    "--field-selector=status.phase!=Running",
                ],
                "description": "Non-running pods",
            },
            {
                "name": "top_nodes",
                "command": ["kubectl", "top", "nodes"],
                "description": "Node resource usage",
            },
            {
                "name": "top_pods_--all-namespaces",
                "command": ["kubectl", "top", "pods", "--all-namespaces"],
                "description": "Pod resource usage",
            },
            {
                "name": "get_componentstatuses",
                "command": ["kubectl", "get", "componentstatuses"],
                "description": "Component health status",
            },
            {
                "name": "get_events_--all-namespaces_--sort-by='.lastTimestamp'",
                "command": [
                    "kubectl",
                    "get",
                    "events",
                    "--all-namespaces",
                    "--sort-by=.lastTimestamp",
                ],
                "description": "Recent cluster events",
            },
            {
                "name": "get_pods_--all-namespaces",
                "command": ["kubectl", "get", "pods", "--all-namespaces", "-o", "wide"],
                "description": "All pods detailed view",
            },
            {
                "name": "get_services_--all-namespaces",
                "command": ["kubectl", "get", "services", "--all-namespaces"],
                "description": "All services",
            },
            {
                "name": "get_deployments_--all-namespaces",
                "command": ["kubectl", "get", "deployments", "--all-namespaces"],
                "description": "All deployments",
            },
        ]

    def run_command(self, command, capture_output=True, timeout=60):
        """Run a shell command and return the result"""
        try:
            logger.info(f"Running: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                check=False,  # Don't raise exception on non-zero exit
            )
            return {
                "command": " ".join(command),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            return {
                "command": " ".join(command),
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error running command {' '.join(command)}: {e}")
            return {
                "command": " ".join(command),
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def setup_minikube(self):
        """Start and configure minikube"""
        logger.info("Setting up minikube...")

        # Stop any existing minikube
        self.run_command(["minikube", "stop"])

        # Delete existing cluster to ensure clean state
        self.run_command(["minikube", "delete"])

        # Start minikube with specific configuration
        start_result = self.run_command(
            ["minikube", "start", "--cpus=4", "--memory=4096", "--disk-size=20g"],
            timeout=300,
        )

        if start_result["returncode"] != 0:
            raise Exception(f"Failed to start minikube: {start_result['stderr']}")

        # Enable metrics server for 'kubectl top' commands
        self.run_command(["minikube", "addons", "enable", "metrics-server"])

        # Wait for metrics server to be ready
        logger.info("Waiting for metrics server to be ready...")
        time.sleep(30)

        # Verify cluster is ready
        ready_result = self.run_command(["kubectl", "get", "nodes"])
        if ready_result["returncode"] != 0:
            raise Exception("Cluster not ready after setup")

        logger.info("Minikube setup complete")

    def deploy_manifests(self, deployment_file, service_file):
        """Deploy Kubernetes manifests"""
        logger.info(f"Deploying manifests: {deployment_file}, {service_file}")

        # Apply deployment
        if deployment_file and Path(deployment_file).exists():
            deploy_result = self.run_command(
                ["kubectl", "apply", "-f", deployment_file]
            )
            if deploy_result["returncode"] != 0:
                logger.error(f"Failed to apply deployment: {deploy_result['stderr']}")

        # Apply service
        if service_file and Path(service_file).exists():
            service_result = self.run_command(["kubectl", "apply", "-f", service_file])
            if service_result["returncode"] != 0:
                logger.error(f"Failed to apply service: {service_result['stderr']}")

        # Wait for deployments to settle
        logger.info("Waiting for deployments to settle...")
        time.sleep(45)

        # Try to wait for deployment rollout (if it exists)
        self.run_command(
            [
                "kubectl",
                "rollout",
                "status",
                "deployment",
                "--all-namespaces",
                "--timeout=60s",
            ]
        )

    def run_assessments(self, scenario_type):
        """Run all assessment commands and save results"""
        logger.info(f"Running {scenario_type} assessments...")

        results = {
            "cluster_id": self.cluster_id,
            "scenario_type": scenario_type,
            "timestamp": datetime.now().isoformat(),
            "assessments": {},
        }

        for assessment in self.assessment_commands:
            logger.info(f"Running assessment: {assessment['name']}")

            # Run the command
            result = self.run_command(assessment["command"])

            # Store the result
            results["assessments"][assessment["name"]] = {
                "description": assessment["description"],
                "result": result,
            }

            # Also save individual flat files
            self.save_flat_file(scenario_type, assessment["name"], result)

        # Save comprehensive JSON results
        results_file = (
            self.output_dir / f"{self.cluster_id}-{scenario_type}-comprehensive.json"
        )
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Assessment results saved to {results_file}")
        return results

    def save_flat_file(self, scenario_type, command_name, result):
        """Save individual command output to flat file"""
        # Create filename based on the pattern from the user's example
        filename = f"{self.cluster_id}-{scenario_type}-kubectl_{command_name}"

        # Save stdout to file
        stdout_file = self.output_dir / f"{filename}.txt"
        with open(stdout_file, "w") as f:
            f.write(f"# Command: {result['command']}\n")
            f.write(f"# Timestamp: {result['timestamp']}\n")
            f.write(f"# Return code: {result['returncode']}\n")
            f.write(f"# Cluster ID: {self.cluster_id}\n")
            f.write(f"# Scenario: {scenario_type}\n")
            f.write("\n--- STDOUT ---\n")
            f.write(result["stdout"])
            if result["stderr"]:
                f.write("\n--- STDERR ---\n")
                f.write(result["stderr"])

        logger.debug(f"Saved flat file: {stdout_file}")

    def cleanup_cluster(self):
        """Clean up cluster resources"""
        logger.info("Cleaning up cluster resources...")

        # Delete all resources in default namespace
        self.run_command(["kubectl", "delete", "all", "--all"])

        # Wait for cleanup
        time.sleep(10)

    def collect_scenario_data(self, deployment_file, service_file, scenario_type):
        """Collect data for a single scenario (sick or healthy)"""
        logger.info(f"Collecting {scenario_type} scenario data...")

        try:
            # Deploy the manifests
            self.deploy_manifests(deployment_file, service_file)

            # Run assessments
            results = self.run_assessments(scenario_type)

            # Clean up for next scenario
            self.cleanup_cluster()

            return results

        except Exception as e:
            logger.error(f"Error in {scenario_type} scenario: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Collect Kubernetes cluster assessment data"
    )
    parser.add_argument("cluster_id", help="Cluster identifier")
    parser.add_argument(
        "--sick-deployment", required=True, help="Path to sick deployment YAML"
    )
    parser.add_argument(
        "--sick-service", required=True, help="Path to sick service YAML"
    )
    parser.add_argument(
        "--healthy-deployment", required=True, help="Path to healthy deployment YAML"
    )
    parser.add_argument(
        "--healthy-service", required=True, help="Path to healthy service YAML"
    )
    parser.add_argument(
        "--output-dir", default="assessment_data", help="Output directory for results"
    )
    parser.add_argument("--skip-sick", action="store_true", help="Skip sick scenario")
    parser.add_argument(
        "--skip-healthy", action="store_true", help="Skip healthy scenario"
    )

    args = parser.parse_args()

    # Initialize collector
    collector = ClusterAssessmentCollector(args.cluster_id, args.output_dir)

    try:
        # Setup minikube
        collector.setup_minikube()

        # Collect sick scenario data
        if not args.skip_sick:
            logger.info("=== COLLECTING SICK SCENARIO DATA ===")
            sick_results = collector.collect_scenario_data(
                args.sick_deployment, args.sick_service, "sick"
            )
            logger.info("Sick scenario data collection complete")

        # Collect healthy scenario data
        if not args.skip_healthy:
            logger.info("=== COLLECTING HEALTHY SCENARIO DATA ===")
            healthy_results = collector.collect_scenario_data(
                args.healthy_deployment, args.healthy_service, "healthy"
            )
            logger.info("Healthy scenario data collection complete")

        logger.info("All data collection complete!")
        logger.info(f"Results saved to: {collector.output_dir}")

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
