# MaxBot Planner Agent

"""
MaxBot Planner Agent - Implementation planning and task breakdown

This agent helps plan complex features, break down tasks into manageable steps,
identify dependencies and risks, and create structured implementation plans.
"""

from typing import Dict, List, Any, Optional
import json

class PlannerAgent:
    """
    Planner Agent for task planning and breakdown
    
    Responsibilities:
    - Analyze requirements and break down into tasks
    - Identify dependencies and potential blockers
    - Estimate complexity and effort
    - Create structured implementation plans
    - Identify risks and mitigation strategies
    """
    
    def __init__(self):
        self.name = "planner"
        self.description = "Implementation planning and task breakdown agent"
        self.skills = [
            "tdd-workflow",
            "code-analysis",
            "python-testing"
        ]
    
    def analyze_task(self, task_description: str, context: Optional[Dict] = None) -> Dict:
        """
        Analyze a task and create a structured plan
        
        Args:
            task_description: Description of the task to plan
            context: Optional context (existing code, constraints, etc.)
            
        Returns:
            Structured plan with tasks, dependencies, and risks
        """
        plan = {
            "task": task_description,
            "phases": [],
            "dependencies": [],
            "risks": [],
            "estimated_effort": "medium",
            "next_steps": []
        }
        
        # Analyze complexity
        complexity = self._estimate_complexity(task_description)
        plan["complexity"] = complexity
        
        # Create phases based on complexity
        if complexity == "low":
            plan["phases"] = self._create_simple_plan(task_description)
        elif complexity == "medium":
            plan["phases"] = self._create_medium_plan(task_description)
        else:
            plan["phases"] = self._create_complex_plan(task_description)
        
        # Identify risks
        plan["risks"] = self._identify_risks(task_description, context)
        
        # Create next steps
        plan["next_steps"] = self._generate_next_steps(plan["phases"])
        
        return plan
    
    def _estimate_complexity(self, task: str) -> str:
        """Estimate task complexity based on description"""
        # Simple heuristics
        if any(word in task.lower() for word in ["fix", "simple", "update", "minor"]):
            return "low"
        elif any(word in task.lower() for word in ["feature", "implement", "add", "new"]):
            return "medium"
        elif any(word in task.lower() for word in ["refactor", "rewrite", "major", "architecture"]):
            return "high"
        else:
            return "medium"
    
    def _create_simple_plan(self, task: str) -> List[Dict]:
        """Create plan for simple tasks"""
        return [
            {
            "phase": "Implementation",
            "tasks": [
                "Write failing test (TDD RED)",
                "Implement minimal solution",
                "Run tests and verify GREEN",
                "Refactor if needed"
            ],
            "skills": ["tdd-workflow"]
            }
        ]
    
    def _create_medium_plan(self, task: str) -> List[Dict]:
        """Create plan for medium complexity tasks"""
        return [
            {
                "phase": "Analysis",
                "tasks": [
                    "Understand requirements",
                    "Analyze existing code",
                    "Identify affected components"
                ],
                "skills": ["code-analysis"]
            },
            {
                "phase": "Design",
                "tasks": [
                    "Design solution architecture",
                    "Define interfaces and data structures",
                    "Plan testing strategy"
                ],
                "skills": ["code-analysis", "python-testing"]
            },
            {
                "phase": "Implementation",
                "tasks": [
                    "Write test suite (TDD RED)",
                    "Implement core functionality",
                    "Run tests and verify GREEN",
                    "Add error handling"
                ],
                "skills": ["tdd-workflow", "python-testing"]
            },
            {
                "phase": "Testing",
                "tasks": [
                    "Verify 80%+ code coverage",
                    "Run integration tests",
                    "Perform manual testing"
                ],
                "skills": ["python-testing"]
            }
        ]
    
    def _create_complex_plan(self, task: str) -> List[Dict]:
        """Create plan for complex tasks"""
        return [
            {
                "phase": "Research",
                "tasks": [
                    "Research existing solutions",
                    "Study similar implementations",
                    "Review best practices"
                ],
                "skills": ["code-analysis"]
            },
            {
                "phase": "Architecture Design",
                "tasks": [
                    "Design system architecture",
                    "Define component boundaries",
                    "Plan data flow and interfaces",
                    "Document design decisions"
                ],
                "skills": ["code-analysis"]
            },
            {
                "phase": "Implementation Planning",
                "tasks": [
                    "Break down into sub-tasks",
                    "Identify dependencies",
                    "Estimate effort per task",
                    "Create timeline"
                ],
                "skills": []
            },
            {
                "phase": "Core Implementation",
                "tasks": [
                    "Implement base infrastructure",
                    "Implement core functionality",
                    "Write comprehensive tests"
                ],
                "skills": ["tdd-workflow", "python-testing"]
            },
            {
                "phase": "Integration",
                "tasks": [
                    "Integrate with existing systems",
                    "Test integration points",
                    "Handle edge cases"
                ],
                "skills": ["python-testing"]
            },
            {
                "phase": "Testing and Validation",
                "tasks": [
                    "Verify 80%+ code coverage",
                    "Run integration tests",
                    "Perform E2E testing",
                    "Security review (security-review skill)"
                ],
                "skills": ["python-testing", "security-review"]
            },
            {
                "phase": "Documentation",
                "tasks": [
                    "Write API documentation",
                    "Update user guides",
                    "Document architecture decisions"
                ],
                "skills": []
            }
        ]
    
    def _identify_risks(self, task: str, context: Optional[Dict]) -> List[Dict]:
        """Identify potential risks"""
        risks = []
        
        # Common risks
        if "new" in task.lower() or "add" in task.lower():
            risks.append({
                "risk": "Integration challenges",
                "impact": "medium",
                "mitigation": "Test integration points early"
            })
        
        if "refactor" in task.lower():
            risks.append({
                "risk": "Breaking existing functionality",
                "impact": "high",
                "mitigation": "Comprehensive test suite before refactoring"
            })
        
        if "api" in task.lower():
            risks.append({
                "risk": "Security vulnerabilities",
                "impact": "high",
                "mitigation": "Use security-review skill"
            })
        
        return risks
    
    def _format_plan(self, plan: Dict) -> str:
        """Format plan for display"""
        output = []
        output.append(f"📋 Plan for: {plan['task']}")
        output.append(f"📊 Complexity: {plan['complexity']}")
        output.append(f"⏱️  Estimated Effort: {plan['estimated_effort']}")
        output.append("")
        
        for i, phase in enumerate(plan["phases"], 1):
            output.append(f"## Phase {i}: {phase['phase']}")
            for j, task in enumerate(phase["tasks"], 1):
                output.append(f"  {j}. {task}")
            if phase["skills"]:
                output.append(f"  Skills: {', '.join(phase['skills'])}")
            output.append("")
        
        if plan["risks"]:
            output.append("## ⚠️  Risks")
            for risk in plan["risks"]:
                output.append(f"  - {risk['risk']} ({risk['impact']})")
                output.append(f"    Mitigation: {risk['mitigation']}")
            output.append("")
        
        if plan["next_steps"]:
            output.append("## Next Steps")
            for i, step in enumerate(plan["next_steps"], 1):
                output.append(f"  {i}. {step}")
        
        return "\n".join(output)
    
    def _generate_next_steps(self, phases: List[Dict]) -> List[str]:
        """Generate immediate next steps from plan"""
        if not phases:
            return []
        
        next_steps = []
        first_phase = phases[0]
        
        for task in first_phase["tasks"]:
            next_steps.append(task)
        
        return next_steps[:3]  # Return top 3 next steps
    
    def create_plan(self, task_description: str, context: Optional[Dict] = None) -> str:
        """
        Create a formatted plan for a task
        
        Args:
            task_description: Description of the task
            context: Optional context information
            
        Returns:
            Formatted plan as string
        """
        plan = self.analyze_task(task_description, context)
        return self._format_plan(plan)
    
    def __repr__(self) -> str:
        return f"PlannerAgent(name='{self.name}', skills={self.skills})"


# Example usage
if __name__ == "__main__":
    planner = PlannerAgent()
    
    # Example tasks
    tasks = [
        "Fix the memory leak in the session store",
        "Add user authentication to the API",
        "Refactor the gateway to use async/await"
    ]
    
    for task in tasks:
        print("=" * 60)
        print(planner.create_plan(task))
        print()
