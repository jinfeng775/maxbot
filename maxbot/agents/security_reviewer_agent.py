# MaxBot Security Reviewer Agent

"""
MaxBot Security Reviewer Agent - Security vulnerability detection and code review

This agent performs comprehensive security reviews, identifies vulnerabilities,
checks for security best practices, and provides remediation guidance.
"""

from typing import Dict, List, Any, Optional
import re

class SecurityReviewerAgent:
    """
    Security Reviewer Agent for security analysis and vulnerability detection
    
    Responsibilities:
    - Scan code for security vulnerabilities
    - Review authentication and authorization
    - Check for secrets and sensitive data exposure
    - Validate input sanitization
    - Review SQL injection and XSS prevention
    - Check dependencies for known vulnerabilities
    """
    
    def __init__(self):
        self.name = "security-reviewer"
        self.description = "Security vulnerability detection and code review agent"
        self.skills = [
            "security-review",
            "code-analysis"
        ]
        
        # Security patterns to detect
        self.security_patterns = {
            "hardcoded_secrets": {
                "patterns": [
                    r"(api_key|api_key|apikey)\s*=\s*['\"][^'\"]+['\"]",
                    r"(password|pwd|passwd)\s*=\s*['\"][^'\"]+['\"]",
                    r"(secret|token|auth)\s*=\s*['\"][^'\"]+['['\"]",
                    r"(aws_access_key|aws_secret)\s*=\s*['\"][^'\"]+['\"]",
                ],
                "severity": "critical",
                "description": "Hardcoded secret detected"
            },
            "sql_injection": {
                "patterns": [
                    rf"(execute|query|raw)\s*\([^)]*\+\s*[\"']\s*\w+",  # String concatenation
                ],
                "severity": "critical",
                "description": "Potential SQL injection vulnerability"
            },
            "command_injection": {
                "patterns": [
                    r"(os\.system|subprocess\.call|subprocess\.run)\s*\([^)]*\+\s*[\"']",
                    r"(exec|eval)\s*\([^)]*\+\s*[\"']",
                ],
                "severity": "critical",
                "description": "Potential command injection vulnerability"
            },
            "xss_risk": {
                "patterns": [
                    r"(innerHTML|outerHTML|document\.write)\s*=\s*[^;]+[^;]+",
                    r"dangerouslySetInnerHTML\s*=\s*{{\s*\_\_html:\s*\w+",
                ],
                "severity": "high",
                "description": "Potential XSS vulnerability"
            },
            "insecure_crypto": {
                "patterns": [
                    r"from\s+crypto\.cipher\s+import\s+(AES|DES|RSA)",
                    r"hashlib\.(md5|sha1)\(",
                ],
                "severity": "medium",
                "description": "Weak cryptographic algorithm"
            },
            "insecure_random": {
                "patterns": [
                    r"random\.random\s*\(\s*\)",
                    r"random\.choice\s*\(\s*\)",
                ],
                "severity": "medium",
                "description": "Insecure random number generation (use secrets module)"
            },
            "debug_enabled": {
                "patterns": [
                    r"DEBUG\s*=\s*True",
                    r"app\.debug\s*=\s*True",
                ],
                "severity": "medium",
                "description": "Debug mode enabled in production"
            }
        }
    
    def review_code(self, code: str, file_path: Optional[str] = None) -> Dict:
        """
        Review code for security vulnerabilities
        
        Args:
            code: Code content to review
            file_path: Optional file path for context
            
        Returns:
            Security review results with findings and recommendations
        """
        results = {
            "file": file_path or "unknown",
            "findings": [],
            "summary": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "total": 0
            },
            "recommendations": []
        }
        
        # Check each security pattern
        for pattern_name, pattern_info in self.security_patterns.items():
            matches = self._check_pattern(code, pattern_info["patterns"])
            
            for match in matches:
                finding = {
                    "type": pattern_name,
                    "severity": pattern_info["severity"],
                    "description": pattern_info["description"],
                    "line": match["line"],
                    "code": match["code"].strip(),
                    "remediation": self._get_remediation(pattern_name)
                }
                
                results["findings"].append(finding)
                results["summary"][pattern_info["severity"]] += 1
                results["summary"]["total"] += 1
        
        # Check for additional security issues
        results["findings"].extend(self._check_authentication(code))
        results["findings"].extend(self._check_input_validation(code))
        results["findings"].extend(self._check_error_handling(code))
        
        # Update summary
        for finding in results["findings"]:
            if finding["severity"] in results["summary"]:
                results["summary"][finding["severity"]] += 1
                results["summary"]["total"] += 1
        
        # Sort findings by severity
        severity_order = ["critical", "high", "medium", "low"]
        results["findings"].sort(
            key=lambda x: 
            severity_order.index(x["severity"]) if x["severity"] in severity_order else 99
        )
        
        return results
    
    def _check_pattern(self, code: str, patterns: List[str]) -> List[Dict]:
        """Check code for matching security patterns"""
        matches = []
        lines = code.split('\n')
        
        for pattern in patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append({
                        "line": i,
                        "code": line,
                        "pattern": pattern
                    })
        
        return matches
    
    def _check_authentication(self, code: str) -> List[Dict]:
        """Check for authentication and authorization issues"""
        findings = []
        
        # Check for missing authentication decorators
        if "def " in code and "@app.route" in code:
            if "@require_auth" not in code and "@login_required" not in code:
                findings.append({
                    "type": "missing_authentication",
                    "severity": "high",
                    "description": "Route without authentication",
                    "line": self._find_line_number(code, "@app.route"),
                    "code": "@app.route(...)",
                    "remediation": "Add authentication decorator to protected routes"
                })
        
        return findings
    
    def _check_input_validation(self, code: str) -> List[Dict]:
        """Check for input validation issues"""
        findings = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for unvalidated request parameters
            if "request.args" in line or "request.form" in line:
                if not any(x in code for x in ["validate", "schema", "pydantic"]):
                    findings.append({
                        "type": "missing_input_validation",
                        "severity": "high",
                        "description": "User input without validation",
                        "line": i,
                        "code": line.strip(),
                        "remediation": "Use pydantic or other validation library for input validation"
                    })
        
        return findings
    
    def _check_error_handling(self, code: str) -> List[Dict]:
        """Check for error handling issues"""
        findings = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for stack trace exposure
            if "except" in line and "print(" in code:
                if "traceback" in code or "stack" in code.lower():
                    findings.append({
                        "type": "stack_trace_exposure",
                        "severity": "medium",
                        "description": "Stack trace exposed to user",
                        "line": i,
                        "code": line.strip(),
                        "remediation": "Log errors server-side, return generic messages to users"
                    })
        
        return findings
    
    def _find_line_number(self, code: str, pattern: str) -> int:
        """Find line number for pattern"""
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if pattern in line:
                return i
        return 0
    
    def _get_remediation(self, pattern_name: str) -> str:
        """Get remediation guidance for pattern"""
        remediations = {
            "hardcoded_secrets": "Move secrets to environment variables or secret manager",
            "sql_injection": "Use parameterized queries or ORM",
            "command_injection": "Use subprocess with list of arguments, not string concatenation",
            "xss_risk": "Sanitize user input before rendering, use output encoding",
            "insecure_crypto": "Use strong cryptography (AES-256, SHA-256+)",
            "insecure_random": "Use secrets module for cryptographic random",
            "debug_enabled": "Disable debug mode in production"
        }
        return remediations.get(pattern_name, "Review and fix security issue")
    
    def review_file(self, file_path: str) -> Dict:
        """
        Review a file for security vulnerabilities
        
        Args:
            file_path: Path to file to review
            
        Returns:
            Security review results
        """
        try:
            with open(file_path, 'r') as f:
                code = f.read()
            
            return self.review_code(code, file_path)
        except FileNotFoundError:
            return {
                "file": file_path,
                "error": "File not found"
            }
    
    def _format_findings(self, results: Dict) -> str:
        """Format security review findings for display"""
        output = []
        
        if results.get("error"):
            output.append(f"❌ Error: {results['error']}")
            return "\n".join(output)
        
        output.append(f"🔒 Security Review for: {results['file']}")
        output.append("")
        
        summary = results["summary"]
        output.append("📊 Summary:")
        output.append(f"  Critical: {summary['critical']}")
        output.append(f"  High: {summary['high']}")
        output.append(f"  Medium: {summary['medium']}")
        output.append(f"  Low: {summary['low']}")
        output.append(f"  Total: {summary['total']}")
        output.append("")
        
        if results["findings"]:
            output.append("🔍 Findings:")
            
            for i, finding in enumerate(results["findings"], 1):
                severity_emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(finding["severity"], "⚪")
                
                output.append(f"\n{i}. {severity_emoji} {finding['description']} ({finding['severity']})")
                output.append(f"   Line {finding['line']}: {finding['code'][:80]}...")
                output.append(f"   💡 Remediación: {finding['remediation']}")
        else:
            output.append("✅ No security issues found!")
        
        return "\n".join(output)
    
    def generate_report(self, results: Dict) -> str:
        """
        Generate a formatted security review report
        
        Args:
            results: Security review results
            
        Returns:
            Formatted report as string
        """
        return self._format_findings(results)
    
    def __repr__(self) -> str:
        return f"SecurityReviewerAgent(name='{self.name}', skills={self.skills})"


# Example usage
if __name__ == "__main__":
    reviewer = SecurityReviewerAgent()
    
    # Example code with security issues
    vulnerable_code = '''
def get_user(user_id):
    import os
    api_key = "sk-proj-1234567890"  # Hardcoded secret
    
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    result = db.execute(query)
    
    return result

def process_command(cmd):
    # Command injection
    os.system(cmd)
    '''
    
    results = reviewer.review_code(vulnerable_code, "vulnerable.py")
    print(results)
