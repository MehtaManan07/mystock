#!/usr/bin/env python3
"""
SQL Performance Analyzer - Static Code Analysis

Analyzes backend service files for SQL/ORM usage patterns and generates numeric metrics.
Produces a numbers-only report for optimization scoping.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


@dataclass
class FunctionMetrics:
    """Numeric metrics for a single function"""
    service_name: str
    function_name: str
    line_start: int
    line_end: int
    
    # Query execution metrics
    db_execute_calls: int = 0
    select_count: int = 0
    insert_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    
    # Query complexity metrics
    filter_predicate_count: int = 0  # where/ilike/in_
    eagerload_count: int = 0  # selectinload/joinedload
    sort_count: int = 0  # order_by
    aggregation_count: int = 0  # sum/count/func
    join_count: int = 0  # join operations
    
    # Performance risk indicators
    loop_db_risk_count: int = 0  # DB ops in loops
    n_plus_1_risk_score: int = 0  # Higher = worse
    
    # Derived metrics
    estimated_query_roundtrips: int = 0
    estimated_cost_score: int = 0
    improvement_priority_score: int = 0


@dataclass
class ServiceMetrics:
    """Aggregated metrics for a service"""
    service_name: str
    function_count: int = 0
    total_db_execute_calls: int = 0
    total_selects: int = 0
    total_inserts: int = 0
    total_updates: int = 0
    total_deletes: int = 0
    total_filters: int = 0
    total_eagerloads: int = 0
    total_sorts: int = 0
    total_aggregations: int = 0
    total_joins: int = 0
    total_loop_risks: int = 0
    avg_cost_score: float = 0.0
    max_priority_score: int = 0


class SQLPatternAnalyzer:
    """Analyzes Python source code for SQL/ORM patterns"""
    
    # SQL-related pattern signatures
    SQL_PATTERNS = {
        'execute': r'db\.execute\(',
        'select': r'select\(',
        'insert': r'db\.add\(|db\.add_all\(',
        'update': r'setattr\(|\.flush\(',
        'delete': r'db\.delete\(',
        'where': r'\.where\(',
        'ilike': r'\.ilike\(',
        'in_': r'\.in_\(',
        'selectinload': r'selectinload\(',
        'joinedload': r'joinedload\(',
        'order_by': r'\.order_by\(',
        'func_sum': r'func\.sum\(',
        'func_count': r'func\.count\(',
        'func_': r'func\.\w+\(',
        'join': r'\.join\(',
    }
    
    @staticmethod
    def count_pattern(code: str, pattern: str) -> int:
        """Count occurrences of a regex pattern in code"""
        return len(re.findall(pattern, code))
    
    @staticmethod
    def detect_loop_db_operations(code: str) -> int:
        """Detect DB operations inside loops (N+1 risk)"""
        risk_count = 0
        lines = code.split('\n')
        in_loop = False
        loop_indent = 0
        
        for line in lines:
            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)
            
            # Track loop entry
            if re.match(r'for\s+\w+\s+in\s+', stripped):
                in_loop = True
                loop_indent = current_indent
            
            # Track loop exit (dedent)
            if in_loop and current_indent <= loop_indent and stripped and not stripped.startswith('#'):
                if not re.match(r'for\s+\w+\s+in\s+', stripped):
                    in_loop = False
            
            # Check for DB operations in loop
            if in_loop:
                if re.search(r'db\.execute\(|db\.add\(|db\.query\(|db\.scalar\(', stripped):
                    risk_count += 1
        
        return risk_count
    
    @staticmethod
    def calculate_n_plus_1_risk(metrics: FunctionMetrics, code: str) -> int:
        """Calculate N+1 query risk score (0-10)"""
        risk_score = 0
        
        # High risk: loops with DB operations
        risk_score += metrics.loop_db_risk_count * 3
        
        # Medium risk: multiple execute calls without eagerload
        if metrics.db_execute_calls > 2 and metrics.eagerload_count == 0:
            risk_score += 2
        
        # Low risk: multiple queries in general
        if metrics.db_execute_calls > 5:
            risk_score += 1
        
        # Positive: eagerload usage reduces risk
        if metrics.eagerload_count > 0:
            risk_score = max(0, risk_score - metrics.eagerload_count)
        
        return min(risk_score, 10)  # Cap at 10
    
    @staticmethod
    def analyze_function(func_name: str, func_code: str, line_start: int, line_end: int, service_name: str) -> FunctionMetrics:
        """Analyze a single function for SQL patterns"""
        metrics = FunctionMetrics(
            service_name=service_name,
            function_name=func_name,
            line_start=line_start,
            line_end=line_end
        )
        
        # Count basic patterns
        metrics.db_execute_calls = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['execute'])
        metrics.select_count = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['select'])
        metrics.insert_count = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['insert'])
        metrics.update_count = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['update'])
        metrics.delete_count = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['delete'])
        
        # Count query complexity patterns
        metrics.filter_predicate_count = (
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['where']) +
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['ilike']) +
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['in_'])
        )
        
        metrics.eagerload_count = (
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['selectinload']) +
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['joinedload'])
        )
        
        metrics.sort_count = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['order_by'])
        
        metrics.aggregation_count = (
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['func_sum']) +
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['func_count']) +
            SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['func_'])
        )
        
        metrics.join_count = SQLPatternAnalyzer.count_pattern(func_code, SQLPatternAnalyzer.SQL_PATTERNS['join'])
        
        # Detect loop risks
        metrics.loop_db_risk_count = SQLPatternAnalyzer.detect_loop_db_operations(func_code)
        
        # Calculate derived metrics
        metrics.n_plus_1_risk_score = SQLPatternAnalyzer.calculate_n_plus_1_risk(metrics, func_code)
        
        # Estimated query roundtrips (conservative estimate)
        metrics.estimated_query_roundtrips = max(
            metrics.db_execute_calls,
            metrics.select_count + metrics.insert_count + metrics.update_count + metrics.delete_count
        )
        
        # Estimated cost score (0-100, higher = more expensive)
        cost = 0
        cost += metrics.db_execute_calls * 5  # Each query has base cost
        cost += metrics.filter_predicate_count * 1  # Filters add complexity
        cost += metrics.join_count * 3  # Joins are expensive
        cost += metrics.aggregation_count * 2  # Aggregations are costly
        cost += metrics.loop_db_risk_count * 20  # Loop queries are very expensive
        cost -= metrics.eagerload_count * 5  # Eagerload reduces cost
        metrics.estimated_cost_score = max(0, cost)
        
        # Improvement priority score (0-100, higher = better target for optimization)
        priority = 0
        priority += metrics.loop_db_risk_count * 15  # High priority: fix N+1
        priority += metrics.n_plus_1_risk_score * 3  # Risk-based priority
        priority += (metrics.db_execute_calls - metrics.eagerload_count) * 2  # Missing eagerload
        if metrics.db_execute_calls > 5:
            priority += 10  # High query count
        if metrics.aggregation_count > 0 and metrics.filter_predicate_count > 5:
            priority += 5  # Complex aggregations
        metrics.improvement_priority_score = min(priority, 100)
        
        return metrics


class ServiceFileAnalyzer:
    """Analyzes a complete service file"""
    
    @staticmethod
    def extract_functions(file_path: Path) -> List[Tuple[str, str, int, int]]:
        """Extract function definitions from a Python file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                line_start = node.lineno
                line_end = node.end_lineno or line_start
                
                # Extract function source code
                lines = source.split('\n')
                func_code = '\n'.join(lines[line_start-1:line_end])
                
                functions.append((func_name, func_code, line_start, line_end))
        
        return functions
    
    @staticmethod
    def analyze_service_file(file_path: Path) -> List[FunctionMetrics]:
        """Analyze all functions in a service file"""
        service_name = file_path.parent.name
        functions = ServiceFileAnalyzer.extract_functions(file_path)
        
        metrics_list = []
        for func_name, func_code, line_start, line_end in functions:
            metrics = SQLPatternAnalyzer.analyze_function(
                func_name, func_code, line_start, line_end, service_name
            )
            metrics_list.append(metrics)
        
        return metrics_list


def aggregate_service_metrics(function_metrics: List[FunctionMetrics]) -> ServiceMetrics:
    """Aggregate function metrics into service-level metrics"""
    if not function_metrics:
        return ServiceMetrics(service_name="unknown")
    
    service_name = function_metrics[0].service_name
    service = ServiceMetrics(service_name=service_name)
    
    service.function_count = len(function_metrics)
    
    for fm in function_metrics:
        service.total_db_execute_calls += fm.db_execute_calls
        service.total_selects += fm.select_count
        service.total_inserts += fm.insert_count
        service.total_updates += fm.update_count
        service.total_deletes += fm.delete_count
        service.total_filters += fm.filter_predicate_count
        service.total_eagerloads += fm.eagerload_count
        service.total_sorts += fm.sort_count
        service.total_aggregations += fm.aggregation_count
        service.total_joins += fm.join_count
        service.total_loop_risks += fm.loop_db_risk_count
        service.max_priority_score = max(service.max_priority_score, fm.improvement_priority_score)
    
    if service.function_count > 0:
        service.avg_cost_score = sum(fm.estimated_cost_score for fm in function_metrics) / service.function_count
    
    return service


def generate_report(all_function_metrics: List[FunctionMetrics], all_service_metrics: List[ServiceMetrics]) -> str:
    """Generate CSV-style numbers-only report"""
    lines = []
    
    # Header
    lines.append("# SQL PERFORMANCE ANALYSIS REPORT")
    lines.append(f"# Generated: {Path(__file__).parent.name}")
    lines.append("")
    
    # Function-level metrics
    lines.append("## FUNCTION-LEVEL METRICS")
    lines.append("service,function,line_start,line_end,db_execute,selects,inserts,updates,deletes,filters,eagerloads,sorts,aggregations,joins,loop_risks,n_plus_1_risk,est_roundtrips,cost_score,priority_score")
    
    for fm in sorted(all_function_metrics, key=lambda x: x.improvement_priority_score, reverse=True):
        lines.append(
            f"{fm.service_name},{fm.function_name},{fm.line_start},{fm.line_end},"
            f"{fm.db_execute_calls},{fm.select_count},{fm.insert_count},{fm.update_count},{fm.delete_count},"
            f"{fm.filter_predicate_count},{fm.eagerload_count},{fm.sort_count},{fm.aggregation_count},{fm.join_count},"
            f"{fm.loop_db_risk_count},{fm.n_plus_1_risk_score},{fm.estimated_query_roundtrips},"
            f"{fm.estimated_cost_score},{fm.improvement_priority_score}"
        )
    
    lines.append("")
    
    # Service-level aggregates
    lines.append("## SERVICE-LEVEL AGGREGATES")
    lines.append("service,functions,db_execute,selects,inserts,updates,deletes,filters,eagerloads,sorts,aggregations,joins,loop_risks,avg_cost,max_priority")
    
    for sm in sorted(all_service_metrics, key=lambda x: x.max_priority_score, reverse=True):
        lines.append(
            f"{sm.service_name},{sm.function_count},{sm.total_db_execute_calls},"
            f"{sm.total_selects},{sm.total_inserts},{sm.total_updates},{sm.total_deletes},"
            f"{sm.total_filters},{sm.total_eagerloads},{sm.total_sorts},{sm.total_aggregations},"
            f"{sm.total_joins},{sm.total_loop_risks},{sm.avg_cost_score:.1f},{sm.max_priority_score}"
        )
    
    lines.append("")
    
    # Global aggregates
    lines.append("## GLOBAL AGGREGATES")
    total_functions = sum(sm.function_count for sm in all_service_metrics)
    total_db_execute = sum(sm.total_db_execute_calls for sm in all_service_metrics)
    total_selects = sum(sm.total_selects for sm in all_service_metrics)
    total_inserts = sum(sm.total_inserts for sm in all_service_metrics)
    total_updates = sum(sm.total_updates for sm in all_service_metrics)
    total_deletes = sum(sm.total_deletes for sm in all_service_metrics)
    total_filters = sum(sm.total_filters for sm in all_service_metrics)
    total_eagerloads = sum(sm.total_eagerloads for sm in all_service_metrics)
    total_sorts = sum(sm.total_sorts for sm in all_service_metrics)
    total_aggregations = sum(sm.total_aggregations for sm in all_service_metrics)
    total_joins = sum(sm.total_joins for sm in all_service_metrics)
    total_loop_risks = sum(sm.total_loop_risks for sm in all_service_metrics)
    global_avg_cost = sum(sm.avg_cost_score for sm in all_service_metrics) / len(all_service_metrics) if all_service_metrics else 0
    global_max_priority = max((sm.max_priority_score for sm in all_service_metrics), default=0)
    
    lines.append("metric,value")
    lines.append(f"total_services,{len(all_service_metrics)}")
    lines.append(f"total_functions,{total_functions}")
    lines.append(f"total_db_execute_calls,{total_db_execute}")
    lines.append(f"total_selects,{total_selects}")
    lines.append(f"total_inserts,{total_inserts}")
    lines.append(f"total_updates,{total_updates}")
    lines.append(f"total_deletes,{total_deletes}")
    lines.append(f"total_filters,{total_filters}")
    lines.append(f"total_eagerloads,{total_eagerloads}")
    lines.append(f"total_sorts,{total_sorts}")
    lines.append(f"total_aggregations,{total_aggregations}")
    lines.append(f"total_joins,{total_joins}")
    lines.append(f"total_loop_risks,{total_loop_risks}")
    lines.append(f"global_avg_cost_score,{global_avg_cost:.1f}")
    lines.append(f"global_max_priority,{global_max_priority}")
    
    return '\n'.join(lines)


def main():
    """Main entry point"""
    # Find all service.py files
    modules_dir = Path(__file__).parent / "app" / "modules"
    service_files = list(modules_dir.glob("*/service.py"))
    
    print(f"Found {len(service_files)} service files")
    
    all_function_metrics: List[FunctionMetrics] = []
    all_service_metrics: List[ServiceMetrics] = []
    
    for service_file in sorted(service_files):
        print(f"Analyzing {service_file.parent.name}/service.py...")
        function_metrics = ServiceFileAnalyzer.analyze_service_file(service_file)
        all_function_metrics.extend(function_metrics)
        
        service_metrics = aggregate_service_metrics(function_metrics)
        all_service_metrics.append(service_metrics)
    
    print(f"\nAnalyzed {len(all_function_metrics)} functions across {len(all_service_metrics)} services")
    
    # Generate report
    report = generate_report(all_function_metrics, all_service_metrics)
    
    # Write to file
    output_path = Path(__file__).parent / "sql-performance-report.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReport written to: {output_path}")
    print(f"Total functions analyzed: {len(all_function_metrics)}")
    print(f"Total services analyzed: {len(all_service_metrics)}")
    
    # Print top optimization targets
    print("\n=== TOP 5 OPTIMIZATION TARGETS ===")
    top_functions = sorted(all_function_metrics, key=lambda x: x.improvement_priority_score, reverse=True)[:5]
    for i, fm in enumerate(top_functions, 1):
        print(f"{i}. {fm.service_name}.{fm.function_name} (priority: {fm.improvement_priority_score}, cost: {fm.estimated_cost_score})")


if __name__ == "__main__":
    main()
