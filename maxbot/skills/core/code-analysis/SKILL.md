---
name: code-analysis
description: Use this skill when analyzing code structure, identifying patterns, reviewing code quality, or understanding codebases. Integrates with MaxBot's file tools for comprehensive code analysis.
category: development
priority: P0
tools_required:
  - file_tools
  - terminal
  - search_files
  - execute_code
dependencies:
  - python-testing
---

# Code Analysis Skill

This skill provides comprehensive code analysis capabilities for MaxBot, including structure analysis, pattern identification, quality assessment, and codebase understanding.

## When to Activate

- Analyzing code structure and organization
- Identifying design patterns and anti-patterns
- Reviewing code quality and maintainability
- Understanding existing codebases
- Refactoring or optimizing code
- Finding code smells and technical debt

## Core Analysis Workflows

### 1. Code Structure Analysis

#### Directory Structure Analysis
```python
# Steps:
1. Use search_files(target='files') to find all Python files
2. Analyze directory organization patterns
3. Identify module relationships
4. Document structure findings

# Example command:
search_files(pattern='*.py', target='files', path='/path/to/project', output_mode='files_only')
```

#### Module Dependency Analysis
```python
# Steps:
1. Read all Python files with read_file
2. Identify import statements (import X, from X import Y)
3. Build dependency graph
4. Identify circular dependencies
5. Document module relationships

# Pattern to match imports:
- ^import\s+(\w+)$
- ^from\s+(\w+)\s+import
```

#### Function and Class Analysis
```python
# Steps:
1. Scan Python files for function/class definitions
2. Analyze signatures, parameters, return types
3. Identify complexity (nesting levels, line count)
4. Document API surface

# Patterns:
- ^def\s+(\w+)\s*\(
- ^class\s+(\w+)\s*(?:\(|:)
- ^async\s+def\s+(\w+)\s*\(
```

### 2. Code Quality Assessment

#### Cyclomatic Complexity Analysis
```python
# Complexity metrics:
- Simple: 1-5
- Moderate: 6-10 (needs review)
- Complex: 11-20 (should refactor)
- Very Complex: 21+ (must refactor)

# Count control flow statements:
if, elif, for, while, except, with, and, or

# Example assessment:
def calculate_score(metrics):
    complexity = 0
    if metrics.get('speed'): complexity += 1
    if metrics.get('accuracy'): complexity += 1
    for key in metrics: complexity += 1
    # Add complexity for each control flow
```

#### Code Duplication Detection
```python
# Steps:
1. Extract code blocks (functions, classes, statements)
2. Normalize code (remove whitespace, variable names)
3. Compare normalized blocks
4. Report duplicates > 80% similarity

# Tools to use:
- difflib.SequenceMatcher
- Levenshtein distance
- Token-based comparison
```

#### Code Smell Detection

**Common Code Smells:**

1. **Long Parameter List** (> 7 parameters)
```python
# BAD
def process_data(data, options, config, auth, cache, logger, metrics):
    pass

# GOOD - Use dataclass or object
@dataclass
class ProcessorConfig:
    data: Any
    options: dict
    config: dict
    auth: Auth
    cache: Cache
    logger: Logger
    metrics: Metrics

def process_data(config: ProcessorConfig):
    pass
```

2. **Long Method** (> 50 lines)
```python
# BAD - Extract smaller methods
def complex_operation(data):
    # 100+ lines of logic
    pass

# GOOD - Decompose
def complex_operation(data):
    validated = validate_data(data)
    processed = process_validated(validated)
    return format_result(processed)
```

3. **Duplicated Code**
```python
# BAD
def process_a(data):
    if not data: return None
    result = []
    for item in data: result.append(item * 2)
    return result

def process_b(data):
    if not data: return None
    result = []
    for item in data: result.append(item * 2)
    return result

# GOOD - Extract common logic
def double_items(data):
    if not data: return None
    return [item * 2 for item in data]
```

4. **Magic Numbers**
```python
# BAD
def calculate_price(price):
    return price * 1.08  # What is 1.08?

# GOOD - Use constants
TAX_RATE = 1.08

def calculate_price(price):
    return price * TAX_RATE
```

5. **Dead Code**
```python
# NEVER called - remove it
def unused_function():
    pass
```

### 3. Pattern Identification

#### Design Pattern Detection

**Singleton Pattern:**
```python
# Pattern: Class with instance control
class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**Factory Pattern:**
```python
# Pattern: Create objects without specifying exact class
class MessageFactory:
    @staticmethod
    def create(message_type: str, content: str):
        if message_type == "text":
            return TextMessage(content)
        elif message_type == "image":
            return ImageMessage(content)
```

**Observer Pattern:**
```python
# Pattern: Subscribe to and notify events
class EventEmitter:
    def __init__(self):
        self._listeners = {}
    
    def on(self, event, callback):
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)
    
    def emit(self, event, *args):
        for callback in self._listeners.get(event, []):
            callback(*args)
```

#### Anti-Pattern Detection

1. **God Object** - Class that does too much
   - Large number of methods (> 20)
   - Handles multiple responsibilities
   - Solution: Break into smaller classes

2. **Shotgun Surgery** - One change requires many files
   - High coupling across modules
   - Solution: Encapsulate related logic

3. **Feature Envy** - Method uses data from another class
   - Solution: Move method to the data owner

### 4. Codebase Understanding

#### Quick Start Guide for New Codebases

```python
# Step 1: Identify entry points
# - Look for main.py, __init__.py, app.py
# - Find setup.py or requirements.txt for dependencies

# Step 2: Understand architecture
# - Check for patterns: MVC, layered, microservices
# - Identify core modules vs utilities

# Step 3: Trace execution flow
# - Start from entry point
# - Follow function calls
# - Document key components

# Step 4: Identify configuration
# - Find .env, config files, settings
# - Understand deployment structure
```

#### Documentation Generation

```python
# Generate API documentation:
1. Scan for functions/classes with docstrings
2. Extract type hints and parameter descriptions
3. Format as Markdown or HTML
4. Include examples if present

# Generate architecture documentation:
1. Map module dependencies
2. Identify layers and boundaries
3. Document data flow
4. Document external integrations
```

### 5. Security Code Analysis

#### Security Pattern Detection

**Authentication/Authorization Issues:**
```python
# BAD - No authentication
def get_user_data(user_id):
    return db.query(f"SELECT * FROM users WHERE id = {user_id}")

# GOOD - Check permissions
@require_authentication
def get_user_data(user_id):
    return db.query(
        "SELECT * FROM users WHERE id = %s",
        (user_id,)
    )
```

**SQL Injection Patterns:**
```python
# BAD - String concatenation
query = f"SELECT * FROM users WHERE name = '{name}'"

# GOOD - Parameterized query
query = "SELECT * FROM users WHERE name = %s"
db.execute(query, (name,))
```

**Secret Exposure:**
```python
# BAD - Hardcoded secret
API_KEY = "sk-proj-***"

# GOOD - Environment variable
API_KEY = os.getenv("API_KEY")
```

## Analysis Workflows

### Workflow 1: Quick Code Review

```python
# 1. Get file list
files = search_files(pattern='*.py', target='files')

# 2. Analyze each file
for file in files:
    content = read_file(file)
    
    # Check length
    if line_count > 500:
        report_issue(f"{file} is too long ({line_count} lines)")
    
    # Check complexity
    complexity = calculate_cyclomatic_complexity(content)
    if complexity > 10:
        report_issue(f"{file} has high complexity ({complexity})")
    
    # Check for code smells
    smells = detect_code_smells(content)
    for smell in smells:
        report_issue(f"{file}: {smell}")

# 3. Generate summary
generate_summary()
```

### Workflow 2: Deep Codebase Analysis

```python
# 1. Build dependency graph
graph = build_dependency_graph(project_path)

# 2. Find circular dependencies
cycles = find_cycles(graph)
if cycles:
    report_critical("Circular dependencies found", cycles)

# 3. Calculate metrics
metrics = {
    "total_files": count_files(),
    "total_lines": count_lines(),
    "avg_complexity": calculate_avg_complexity(),
    "test_coverage": get_coverage(),
    "duplication_rate": find_duplicates()
}

# 4. Generate comprehensive report
generate_analysis_report(metrics)
```

### Workflow 3: Refactoring Planning

```python
# 1. Identify refactoring candidates
candidates = []

for file in files:
    if has_long_methods(file):
        candidates.append({
            "file": file,
            "type": "extract_method",
            "priority": "high"
        })
    
    if has_duplicates(file):
        candidates.append({
            "file": file,
            "type": "extract_common",
            "priority": "medium"
        })

# 2. Prioritize by impact
candidates.sort(key=lambda x: x["priority"], reverse=True)

# 3. Generate refactoring plan
for candidate in candidates:
    print(f"Refactor {candidate['file']}: {candidate['type']}")
```

## Reporting Formats

### Summary Report

```markdown
# Code Analysis Report

## Metrics
- Total Files: 50
- Total Lines: 12,500
- Average Complexity: 4.2
- Test Coverage: 78%
- Duplication Rate: 3%

## Issues Found
### Critical (3)
- Circular dependency: A -> B -> C -> A
- SQL injection vulnerability in user_service.py:45
- Hardcoded secret in config.py:12

### High Priority (5)
- Method complexity > 15 in data_processor.py
- Long parameter list in api_client.py
- Duplicated code in utils.py

### Medium Priority (8)
- Missing docstrings for public APIs
- Inconsistent naming conventions

## Recommendations
1. Fix circular dependencies immediately
2. Address SQL injection vulnerability
3. Refactor high-complexity methods
4. Increase test coverage to 80%+
```

## Integration with MaxBot Tools

### Using read_file

```python
# Read file content
content = read_file('maxbot/gateway/session.py')

# Analyze content
analyze_code(content)
```

### Using search_files

```python
# Find all Python files
files = search_files(
    pattern='*.py',
    target='files',
    path='maxbot'
)

# Analyze each file
for file in files:
    analyze_file(file)
```

### Using execute_code

```python
# Run analysis tools
result = execute_code('''
import radon.cli as radon_cli

# Analyze complexity
radon_cli.main(['cc', 'maxbot/', '-a'])
''')
```

## Best Practices

### For Code Analysis

1. **Start broad, then narrow** - Understand structure first, then details
2. **Use automation** - Don't manually analyze large codebases
3. **Focus on high-impact issues** - Prioritize critical and high priority
4. **Document findings** - Create actionable reports
5. **Track metrics over time** - Monitor trends and improvements

### For Refactoring

1. **Test first** - Ensure tests pass before refactoring (use tdd-workflow)
2. **Small changes** - Refactor incrementally
3. **Verify** - Run tests after each change
4. **Commit** - Save working state after each refactor

## Tools and Libraries

### Static Analysis Tools

- **radon** - Complexity metrics
- **pylint** - Code quality analysis
- **pyflakes** - Error checking
- **mypy** - Type checking
- **bandit** - Security analysis

### Installation

```bash
pip install radon pylint pyflakes mypy bandit

# Run tools
radon cc maxbot/ -a  # Complexity
pylint maxbot/        # Quality
mypy maxbot/          # Type checking
bandit -r maxbot/     # Security
```

## Quick Reference

| Analysis Type | Tool | Command |
|--------------|------|----------|
| Complexity | radon | `radon cc <path> -a` |
| Quality | pylint | `pylint <path>` |
| Type Checking | mypy | `mypy <path>` |
| Security | bandit | `bandit -r <path>` |
| Duplicates | clone-detection | Custom tool |

---

**Remember**: Code analysis is about understanding, not just collecting metrics. Focus on actionable insights that improve code quality and maintainability.

**MaxBot-Specific Notes**:
- Use MaxBot's file tools for code access
- Use search_files for large-scale analysis
- Use execute_code for running analysis tools
- Integrate with security-review skill for security analysis
- Report findings in chat-friendly format for messaging platforms
