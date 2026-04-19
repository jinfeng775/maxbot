# MaxBot Security Review System

"""
Security Review System for MaxBot - Integrated security checking and vulnerability scanning

This system provides automated security reviews, integrates with code changes,
and ensures security best practices are followed across the codebase.
"""

from typing import Dict, List, Any, Optional
import os
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SecurityCheck:
    """Security check configuration"""
    name: str
    command: List[str]
    severity: str  # critical, high, medium, low
    enabled: bool = True


class SecurityReviewSystem:
    """
    Automated security review system for MaxBot

    Features:
    - Automated security scanning on code changes
    - Integration with external security tools (bandit, safety, pip-audit)
    - Pre-commit hooks for security checks
    - Vulnerability database tracking
    - Security policy enforcement
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.security_reviewer_agent = None  # Will be initialized on demand

        # Security tools configuration
        self.security_checks = {
            "bandit": SecurityCheck(
                name="bandit",
                command=["bandit", "-r", "maxbot/", "-f", "json"],
                severity="high",
                enabled=True
            ),
            "safety": SecurityCheck(
                name="safety",
                command=["safety", "check", "--json"],
                severity="high",
                enabled=True
            ),
            "pip-audit": SecurityCheck(
                name="pip-audit",
                command=["pip-audit", "--format", "json"],
                severity="medium",
                enabled=True
            ),
            "mypy": SecurityCheck(
                name="mypy",
                command=["mypy", "maxbot/", "--json-report", "/tmp/mypy-report.json"],
                severity="low",
                enabled=False
            )
        }

        # Security policy settings
        self.security_policy = {
            "fail_on_critical": True,
            "fail_on_high": True,
            "require_auth_checks": True,
            "require_input_validation": True,
            "max_severity_allowed": "medium"  # max allowed in CI/CD
        }

    def run_security_scan(self, check_name: Optional[str] = None) -> Dict:
        """
        Run security scans on the codebase

        Args:
            check_name: Specific security check to run (or None for all)

        Returns:
            Combined security scan results
        """
        results = {
            "checks_run": [],
            "total_issues": 0,
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "findings": [],
            "scan_failures": [],
            "passed": True
        }

        if check_name:
            checks_to_run = [check_name]
        else:
            checks_to_run = list(self.security_checks.keys())

        for check_name in checks_to_run:
            if check_name not in self.security_checks:
                failure = {
                    "check": check_name,
                    "error": f"Unknown security check: {check_name}",
                    "severity": "high",
                }
                results["scan_failures"].append(failure)
                results["findings"].append(dict(failure))
                continue

            check = self.security_checks[check_name]
            if not check.enabled:
                continue

            check_result = self._run_security_check(check)
            results["checks_run"].append(check_name)

            if check_result["success"]:
                results["findings"].extend(check_result["findings"])
                results["by_severity"][check.severity] += len(check_result["findings"])
                results["total_issues"] += len(check_result["findings"])
            else:
                failure = {
                    "check": check_name,
                    "error": check_result["error"],
                    "severity": check.severity,
                }
                results["scan_failures"].append(failure)
                results["findings"].append(dict(failure))

        # Determine if scan passed
        results["passed"] = self._evaluate_scan_results(results)

        return results
    
    def _run_security_check(self, check: SecurityCheck) -> Dict:
        """Run a single security check"""
        try:
            result = subprocess.run(
                check.command,
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "findings": [],
                    "output": result.stdout
                }
            
            # Parse output for findings
            findings = self._parse_check_output(check.name, result.stdout, result.stderr)
            
            return {
                "success": True,
                "findings": findings,
                "output": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Security check '{check.name}' timed out",
                "findings": []
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Security tool '{check.name}' not installed",
                "findings": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "findings": []
            }
    
    def _parse_check_output(self, check_name: str, stdout: str, stderr: str) -> List[Dict]:
        """Parse security check output for findings"""
        findings = []
        
        try:
            if check_name == "bandit":
                findings.extend(self._parse_bandit_output(stdout))
            elif check_name == "safety":
                findings.extend(self._parse_safety_output(stdout))
            elif check_name == "pip-audit":
                findings.extend(self._parse_pip_audit_output(stdout))
        except Exception as e:
            # If parsing fails, return raw output as a finding
            findings.append({
                "check": check_name,
                "message": f"Failed to parse output: {str(e)}",
                "raw_output": stdout
            })
        
        return findings
    
    def _parse_bandit_output(self, output: str) -> List[Dict]:
        """Parse bandit security tool output"""
        findings = []
        
        try:
            data = json.loads(output)
            
            if "results" in data:
                for result in data["results"]:
                    findings.append({
                        "check": "bandit",
                        "test_id": result.get("test_id"),
                        "severity": self._map_bandit_severity(result.get("issue_severity")),
                        "message": result.get("issue_text"),
                        "file": result.get("filename"),
                        "line": result.get("line_number"),
                        "code": result.get("code")
                    })
        except json.JSONDecodeError:
            pass
        
        return findings
    
    def _parse_safety_output(self, output: str) -> List[Dict]:
        """Parse safety vulnerability scanner output"""
        findings = []
        
        try:
            data = json.loads(output)
            
            if isinstance(data, list):
                for vuln in data:
                    findings.append({
                        "check": "safety",
                        "severity": "high",
                        "message": vuln.get("message", "Vulnerability found"),
                        "package": vuln.get("package"),
                        "version": vuln.get("version"),
                        "advisory": vuln.get("advisory")
                    })
        except json.JSONDecodeError:
            pass
        
        return findings
    
    def _parse_pip_audit_output(self, output: str) -> List[Dict]:
        """Parse pip-audit output"""
        findings = []
        
        try:
            data = json.loads(output)
            
            if isinstance(data, list):
                for vuln in data:
                    findings.append({
                        "check": "pip-audit",
                        "severity": "medium",
                        "message": f"Vulnerability in {vuln.get('name')}",
                        "package": vuln.get("name"),
                        "installed_version": vuln.get("installed_version"),
                        "affected_versions": vuln.get("affected_versions")
                    })
        except json.JSONDecodeError:
            pass
        
        return findings
    
    def _map_bandit_severity(self, severity: Optional[str]) -> str:
        """Map bandit severity to standard levels"""
        mapping = {
            "HIGH": "critical",
            "MEDIUM": "high",
            "LOW": "medium"
        }
        return mapping.get(severity, "low")
    
    def _evaluate_scan_results(self, results: Dict) -> bool:
        """Evaluate if scan results pass based on security policy"""
        if results.get("scan_failures"):
            return False

        policy = self.security_policy

        if policy["fail_on_critical"] and results["by_severity"]["critical"] > 0:
            return False

        if policy["fail_on_high"] and results["by_severity"]["high"] > 0:
            return False

        max_allowed = policy["max_severity_allowed"]
        severity_order = ["low", "medium", "high", "critical"]
        max_index = severity_order.index(max_allowed)

        for severity in severity_order:
            if severity_order.index(severity) > max_index and results["by_severity"][severity] > 0:
                return False

        return True
    
    def review_before_commit(self, files_changed: List[str]) -> Dict:
        """
        Review files before commit
        
        Args:
            files_changed: List of files changed in the commit
            
        Returns:
            Review results with approval status
        """
        results = {
            "approved": True,
            "files_reviewed": [],
            "security_issues": [],
            "recommendations": []
        }
        
        # Initialize security reviewer agent if needed
        if self.security_reviewer_agent is None:
            from maxbot.agents.security_reviewer_agent import SecurityReviewerAgent
            self.security_reviewer_agent = SecurityReviewerAgent()
        
        # Review each changed file
        for file_path in files_changed:
            if not file_path.endswith('.py'):
                continue
            
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            review_result = self.security_reviewer_agent.review_file(str(full_path))
            
            results["files_reviewed"].append({
                "file": file_path,
                "review": review_result
            })
            
            if review_result.get("summary", {}).get("critical", 0) > 0:
                results["approved"] = False
                results["security_issues"].append({
                    "file": file_path,
                    "issues": review_result.get("findings", [])
                })
        
        return results
    
    def generate_pre_commit_hook(self, output_path: str = None) -> str:
        """
        Generate pre-commit hook script
        
        Args:
            output_path: Path to save hook script (or None to return content)
            
        Returns:
            Hook script content
        """
        hook_content = '''#!/bin/bash
# MaxBot Security Pre-Commit Hook

echo "Running security checks..."

# Run bandit
echo "Running bandit security check..."
bandit -r maxbot/ -f json -o /tmp/bandit-report.json
BANDIT_EXIT=$?

if [ $BANDIT_EXIT -ne 0 ]; then
    echo "❌ Bandit found security issues:"
    cat /tmp/bandit-report.json | jq '.results[] | {file: .filename, line: .line_number, severity: .issue_severity, message: .issue_text}'
    echo ""
    echo "💡 Run 'bandit -r maxbot/' to see full report"
    exit 1
fi

echo "✅ Security checks passed. Proceeding with commit..."
'''
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(hook_content)
            os.chmod(output_path, 0o755)
        
        return hook_content
    
    def format_security_report(self, results: Dict) -> str:
        """Format security scan results for display"""
        output = []
        
        output.append("🔒 Security Scan Results")
        output.append("=" * 50)
        output.append("")
        
        if results["passed"]:
            output.append("✅ Security scan PASSED")
        else:
            output.append("❌ Security scan FAILED")
        
        output.append("")
        output.append("📊 Summary:")
        output.append(f"  Checks Run: {', '.join(results['checks_run'])}")
        output.append(f"  Total Issues: {results['total_issues']}")
        output.append(f"  Critical: {results['by_severity']['critical']} 🔴")
        output.append(f"  High: {results['by_severity']['high']} 🟠")
        output.append(f"  Medium: {results['by_severity']['medium']} 🟡")
        output.append(f"  Low: {results['by_severity']['low']} 🟢")
        output.append("")
        
        if results["findings"]:
            output.append("🔍 Findings:")
            
            for i, finding in enumerate(results["findings"], 1):
                severity = finding.get("severity", "low")
                emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(severity, "⚪")
                
                output.append(f"\n{i}. {emoji} {finding.get('check', 'unknown')}: {finding.get('message', 'No message')}")
                
                if "file" in finding:
                    output.append(f"   File: {finding['file']}")
                if "line" in finding:
                    output.append(f"   Line: {finding['line']}")
                if "package" in finding:
                    output.append(f"   Package: {finding['package']}")
        else:
            output.append("✅ No security issues found!")
        
        output.append("")
        
        if not results["passed"]:
            output.append("⚠️  Security scan failed. Please fix critical and high severity issues.")
            output.append("💡 Run individual checks for more details:")
            output.append("   - bandit: bandit -r maxbot/")
            output.append("   - safety: safety check")
            output.append("   - pip-audit: pip-audit")
        
        return "\n".join(output)
    
    def __repr__(self) -> str:
        return f"SecurityReviewSystem(project_root='{self.project_root}')"


# Example usage
if __name__ == "__main__":
    system = SecurityReviewSystem("/root/maxbot")
    
    # Run security scan
    print("Running security scan...")
    results = system.run_security_scan()
    print(system.format_security_report(results))
    
    # Generate pre-commit hook
    hook = system.generate_pre_commit_hook("/tmp/pre-commit-security")
    print(f"\nPre-commit hook generated: {hook}")
