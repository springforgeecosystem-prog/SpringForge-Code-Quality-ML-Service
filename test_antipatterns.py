# import requests
# import json
# from datetime import datetime

# # Configuration
# API_URL = "http://127.0.0.1:8081/predict-antipattern"
# OUTPUT_FILE = "test_results.txt"

# # Test payloads
# test_cases = [
#     {
#         "name": "1. LAYERED - Layer Skip",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.92,
#             "loc": 95.0,
#             "methods": 4.0,
#             "classes": 1.0,
#             "avg_cc": 1.8,
#             "imports": 12.0,
#             "annotations": 8.0,
#             "controller_deps": 0.0,
#             "service_deps": 0.0,
#             "repository_deps": 2.0,
#             "entity_deps": 1.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 3.0,
#             "has_business_logic": True,
#             "has_data_access": True,
#             "has_http_handling": True,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": True
#         },
#         "expected": "layer_skip_in_layered"
#     },
#     {
#         "name": "2. LAYERED - Reversed Dependency",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.88,
#             "loc": 145.0,
#             "methods": 6.0,
#             "classes": 1.0,
#             "avg_cc": 2.3,
#             "imports": 18.0,
#             "annotations": 10.0,
#             "controller_deps": 1.0,
#             "service_deps": 0.0,
#             "repository_deps": 1.0,
#             "entity_deps": 0.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 2.0,
#             "has_business_logic": True,
#             "has_data_access": True,
#             "has_http_handling": False,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": True
#         },
#         "expected": "reversed_dependency_in_layered"
#     },
#     {
#         "name": "3. LAYERED - Missing Transaction",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.95,
#             "loc": 130.0,
#             "methods": 5.0,
#             "classes": 1.0,
#             "avg_cc": 1.9,
#             "imports": 15.0,
#             "annotations": 7.0,
#             "controller_deps": 0.0,
#             "service_deps": 0.0,
#             "repository_deps": 2.0,
#             "entity_deps": 0.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 2.0,
#             "has_business_logic": True,
#             "has_data_access": True,
#             "has_http_handling": False,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": False
#         },
#         "expected": "missing_transaction_in_layered"
#     },
#     {
#         "name": "4. HEXAGONAL - Missing Port/Adapter",
#         "payload": {
#             "architecture_pattern": "hexagonal",
#             "architecture_confidence": 0.82,
#             "loc": 165.0,
#             "methods": 7.0,
#             "classes": 1.0,
#             "avg_cc": 2.5,
#             "imports": 20.0,
#             "annotations": 12.0,
#             "controller_deps": 0.0,
#             "service_deps": 0.0,
#             "repository_deps": 2.0,
#             "entity_deps": 1.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 3.0,
#             "has_business_logic": True,
#             "has_data_access": True,
#             "has_http_handling": False,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": True
#         },
#         "expected": "missing_port_adapter_in_hexagonal"
#     },
#     {
#         "name": "5. HEXAGONAL - Framework Dependency",
#         "payload": {
#             "architecture_pattern": "hexagonal",
#             "architecture_confidence": 0.78,
#             "loc": 110.0,
#             "methods": 4.0,
#             "classes": 1.0,
#             "avg_cc": 1.6,
#             "imports": 22.0,
#             "annotations": 15.0,
#             "controller_deps": 0.0,
#             "service_deps": 1.0,
#             "repository_deps": 1.0,
#             "entity_deps": 0.0,
#             "adapter_deps": 0.0,
#             "port_deps": 1.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 3.0,
#             "has_business_logic": True,
#             "has_data_access": False,
#             "has_http_handling": False,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": False
#         },
#         "expected": "framework_dependency_in_domain_hexagonal"
#     },
#     {
#         "name": "6. CLEAN - Outer Depends on Inner",
#         "payload": {
#             "architecture_pattern": "clean_architecture",
#             "architecture_confidence": 0.72,
#             "loc": 102.0,
#             "methods": 5.0,
#             "classes": 1.0,
#             "avg_cc": 2.0,
#             "imports": 14.0,
#             "annotations": 9.0,
#             "controller_deps": 0.0,
#             "service_deps": 0.0,
#             "repository_deps": 1.0,
#             "entity_deps": 2.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 3.0,
#             "has_business_logic": True,
#             "has_data_access": True,
#             "has_http_handling": True,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": True
#         },
#         "expected": "outer_depends_on_inner_clean"
#     },
#     {
#         "name": "7. COMMON - Broad Exception Catch",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.90,
#             "loc": 75.0,
#             "methods": 3.0,
#             "classes": 1.0,
#             "avg_cc": 1.5,
#             "imports": 8.0,
#             "annotations": 5.0,
#             "controller_deps": 0.0,
#             "service_deps": 1.0,
#             "repository_deps": 0.0,
#             "entity_deps": 0.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 1.0,
#             "has_business_logic": True,
#             "has_data_access": False,
#             "has_http_handling": False,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": False
#         },
#         "expected": "broad_catch"
#     },
#     {
#         "name": "8. COMMON - No Validation",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.93,
#             "loc": 68.0,
#             "methods": 2.0,
#             "classes": 1.0,
#             "avg_cc": 1.3,
#             "imports": 7.0,
#             "annotations": 4.0,
#             "controller_deps": 0.0,
#             "service_deps": 1.0,
#             "repository_deps": 0.0,
#             "entity_deps": 1.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 2.0,
#             "has_business_logic": False,
#             "has_data_access": False,
#             "has_http_handling": True,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": False
#         },
#         "expected": "no_validation"
#     },
#     {
#         "name": "9. COMMON - Tight Coupling",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.87,
#             "loc": 92.0,
#             "methods": 4.0,
#             "classes": 1.0,
#             "avg_cc": 1.7,
#             "imports": 10.0,
#             "annotations": 6.0,
#             "controller_deps": 0.0,
#             "service_deps": 0.0,
#             "repository_deps": 1.0,
#             "entity_deps": 0.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 1.0,
#             "has_business_logic": True,
#             "has_data_access": True,
#             "has_http_handling": False,
#             "has_validation": False,
#             "has_transaction": False,
#             "violates_layer_separation": False
#         },
#         "expected": "tight_coupling_new_keyword"
#     },
#     {
#         "name": "10. CLEAN CODE - No Anti-patterns",
#         "payload": {
#             "architecture_pattern": "layered",
#             "architecture_confidence": 0.96,
#             "loc": 55.0,
#             "methods": 2.0,
#             "classes": 1.0,
#             "avg_cc": 1.1,
#             "imports": 6.0,
#             "annotations": 4.0,
#             "controller_deps": 0.0,
#             "service_deps": 1.0,
#             "repository_deps": 0.0,
#             "entity_deps": 0.0,
#             "adapter_deps": 0.0,
#             "port_deps": 0.0,
#             "usecase_deps": 0.0,
#             "gateway_deps": 0.0,
#             "total_cross_layer_deps": 1.0,
#             "has_business_logic": False,
#             "has_data_access": False,
#             "has_http_handling": True,
#             "has_validation": True,
#             "has_transaction": False,
#             "violates_layer_separation": False
#         },
#         "expected": "clean"
#     }
# ]

# def run_tests():
#     """Run all test cases and generate report"""
    
#     print("="*80)
#     print("SPRINGFORGE ANTI-PATTERN MODEL - AUTOMATED TESTING")
#     print("="*80)
#     print(f"\nStarting tests at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#     print(f"API Endpoint: {API_URL}")
#     print(f"Total test cases: {len(test_cases)}\n")
    
#     results = []
#     passed = 0
#     failed = 0
    
#     for i, test in enumerate(test_cases, 1):
#         print(f"\n{'='*80}")
#         print(f"Test {i}/{len(test_cases)}: {test['name']}")
#         print(f"{'='*80}")
        
#         try:
#             # Make API request
#             response = requests.post(API_URL, json=test['payload'], timeout=10)
            
#             if response.status_code == 200:
#                 result = response.json()
#                 predicted = result.get('anti_pattern', 'UNKNOWN')
#                 expected = test['expected']
                
#                 # Check if prediction matches expected
#                 status = "✅ PASS" if predicted == expected else "❌ FAIL"
#                 if predicted == expected:
#                     passed += 1
#                 else:
#                     failed += 1
                
#                 print(f"Status: {status}")
#                 print(f"Expected: {expected}")
#                 print(f"Predicted: {predicted}")
                
#                 # Store result
#                 results.append({
#                     'test_name': test['name'],
#                     'expected': expected,
#                     'predicted': predicted,
#                     'status': 'PASS' if predicted == expected else 'FAIL',
#                     'http_status': response.status_code
#                 })
                
#             else:
#                 print(f"❌ HTTP Error: {response.status_code}")
#                 print(f"Response: {response.text}")
#                 failed += 1
#                 results.append({
#                     'test_name': test['name'],
#                     'expected': test['expected'],
#                     'predicted': 'ERROR',
#                     'status': 'ERROR',
#                     'http_status': response.status_code
#                 })
                
#         except requests.exceptions.RequestException as e:
#             print(f"❌ Connection Error: {str(e)}")
#             failed += 1
#             results.append({
#                 'test_name': test['name'],
#                 'expected': test['expected'],
#                 'predicted': 'CONNECTION_ERROR',
#                 'status': 'ERROR',
#                 'http_status': 0
#             })
    
#     # Generate summary report
#     print(f"\n{'='*80}")
#     print("TEST SUMMARY")
#     print(f"{'='*80}")
#     print(f"Total Tests: {len(test_cases)}")
#     print(f"Passed: {passed} ({passed/len(test_cases)*100:.1f}%)")
#     print(f"Failed: {failed} ({failed/len(test_cases)*100:.1f}%)")
#     print(f"Accuracy: {passed/len(test_cases)*100:.1f}%")
    
#     # Save detailed report
#     with open(OUTPUT_FILE, 'w') as f:
#         f.write("SPRINGFORGE ANTI-PATTERN MODEL - TEST REPORT\n")
#         f.write("="*80 + "\n\n")
#         f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#         f.write(f"API Endpoint: {API_URL}\n\n")
        
#         f.write(f"SUMMARY:\n")
#         f.write(f"Total Tests: {len(test_cases)}\n")
#         f.write(f"Passed: {passed}\n")
#         f.write(f"Failed: {failed}\n")
#         f.write(f"Accuracy: {passed/len(test_cases)*100:.1f}%\n\n")
        
#         f.write("="*80 + "\n")
#         f.write("DETAILED RESULTS:\n")
#         f.write("="*80 + "\n\n")
        
#         for i, result in enumerate(results, 1):
#             f.write(f"{i}. {result['test_name']}\n")
#             f.write(f"   Status: {result['status']}\n")
#             f.write(f"   Expected: {result['expected']}\n")
#             f.write(f"   Predicted: {result['predicted']}\n")
#             f.write(f"   HTTP Status: {result['http_status']}\n\n")
    
#     print(f"\n📄 Detailed report saved to: {OUTPUT_FILE}")
#     print("="*80)
    
#     return results

# if __name__ == "__main__":
#     try:
#         results = run_tests()
#     except KeyboardInterrupt:
#         print("\n\n⚠️  Testing interrupted by user")
#     except Exception as e:
#         print(f"\n\n❌ Unexpected error: {str(e)}")
#         import traceback
#         traceback.print_exc()


#test_antipatterns.py
import requests
import json
from datetime import datetime

# Configuration
API_URL = "http://127.0.0.1:8081/predict-antipattern"
OUTPUT_FILE = "test_results.txt"

# Expanded Test payloads - 35 Test Cases
test_cases = [
    # ==========================================
    # LAYERED ARCHITECTURE TESTS (9 cases)
    # ==========================================
    {
        "name": "1. LAYERED - Layer Skip (Controller -> Repository)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.92,
            "loc": 95.0, "methods": 4.0, "classes": 1.0, "avg_cc": 1.8,
            "imports": 12.0, "annotations": 8.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 2.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "layer_skip_in_layered"
    },
    {
        "name": "2. LAYERED - Layer Skip (Multiple Repositories)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.88,
            "loc": 150.0, "methods": 6.0, "classes": 1.0, "avg_cc": 2.5,
            "imports": 18.0, "annotations": 12.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 3.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 5.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": True, "has_validation": True,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "layer_skip_in_layered"
    },
    {
        "name": "3. LAYERED - Reversed Dependency (Service -> Controller)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.90,
            "loc": 145.0, "methods": 6.0, "classes": 1.0, "avg_cc": 2.3,
            "imports": 18.0, "annotations": 10.0,
            "controller_deps": 2.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "reversed_dependency_in_layered"
    },
    {
        "name": "4. LAYERED - Business Logic in Controller (Complex)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.95,
            "loc": 180.0, "methods": 8.0, "classes": 1.0, "avg_cc": 3.5,
            "imports": 15.0, "annotations": 9.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "business_logic_in_controller_layered"
    },
    {
        "name": "5. LAYERED - Business Logic in Controller (Moderate)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.89,
            "loc": 120.0, "methods": 5.0, "classes": 1.0, "avg_cc": 2.8,
            "imports": 11.0, "annotations": 7.0,
            "controller_deps": 0.0, "service_deps": 2.0, "repository_deps": 0.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": True, "has_validation": True,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "business_logic_in_controller_layered"
    },
    {
        "name": "6. LAYERED - Missing Transaction (Single Repository)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.94,
            "loc": 130.0, "methods": 5.0, "classes": 1.0, "avg_cc": 1.9,
            "imports": 15.0, "annotations": 7.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "missing_transaction_in_layered"
    },
    {
        "name": "7. LAYERED - Missing Transaction (Multiple Operations)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.91,
            "loc": 200.0, "methods": 8.0, "classes": 1.0, "avg_cc": 2.4,
            "imports": 20.0, "annotations": 10.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 3.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 4.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "missing_transaction_in_layered"
    },
    {
        "name": "8. LAYERED - Clean Service Layer",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.93,
            "loc": 85.0, "methods": 4.0, "classes": 1.0, "avg_cc": 1.5,
            "imports": 12.0, "annotations": 8.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": True, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    {
        "name": "9. LAYERED - Clean Controller",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.96,
            "loc": 55.0, "methods": 2.0, "classes": 1.0, "avg_cc": 1.1,
            "imports": 6.0, "annotations": 5.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": True, "has_validation": True,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    
    # ==========================================
    # HEXAGONAL ARCHITECTURE TESTS (9 cases)
    # ==========================================
    {
        "name": "10. HEXAGONAL - Missing Port/Adapter (Service -> Repository)",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.82,
            "loc": 165.0, "methods": 7.0, "classes": 1.0, "avg_cc": 2.5,
            "imports": 20.0, "annotations": 12.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 2.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "missing_port_adapter_in_hexagonal"
    },
    {
        "name": "11. HEXAGONAL - Missing Port/Adapter (Complex Domain)",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.78,
            "loc": 220.0, "methods": 10.0, "classes": 2.0, "avg_cc": 3.1,
            "imports": 25.0, "annotations": 15.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 3.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 6.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "missing_port_adapter_in_hexagonal"
    },
    {
        "name": "12. HEXAGONAL - Framework Dependency (Spring Annotations)",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.80,
            "loc": 110.0, "methods": 4.0, "classes": 1.0, "avg_cc": 1.6,
            "imports": 22.0, "annotations": 15.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 1.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 1.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "framework_dependency_in_domain_hexagonal"
    },
    {
        "name": "13. HEXAGONAL - Framework Dependency (JPA Entities)",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.75,
            "loc": 95.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.4,
            "imports": 18.0, "annotations": 12.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 1.0, "port_deps": 1.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 2.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "framework_dependency_in_domain_hexagonal"
    },
    {
        "name": "14. HEXAGONAL - Adapter Without Port",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.85,
            "loc": 88.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.4,
            "imports": 10.0, "annotations": 6.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 0.0, "adapter_deps": 1.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 2.0,
            "has_business_logic": False, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "adapter_without_port_hexagonal"
    },
    {
        "name": "15. HEXAGONAL - Clean Port Implementation",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.91,
            "loc": 72.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.3,
            "imports": 8.0, "annotations": 5.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 1.0, "port_deps": 2.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    {
        "name": "16. HEXAGONAL - Clean Adapter",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.87,
            "loc": 105.0, "methods": 5.0, "classes": 1.0, "avg_cc": 1.7,
            "imports": 12.0, "annotations": 7.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 1.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": False, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    {
        "name": "17. HEXAGONAL - Domain Service (Clean)",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.84,
            "loc": 140.0, "methods": 6.0, "classes": 1.0, "avg_cc": 2.2,
            "imports": 14.0, "annotations": 6.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 2.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 4.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    {
        "name": "18. HEXAGONAL - Infrastructure Layer",
        "payload": {
            "architecture_pattern": "hexagonal",
            "architecture_confidence": 0.89,
            "loc": 95.0, "methods": 4.0, "classes": 1.0, "avg_cc": 1.5,
            "imports": 16.0, "annotations": 9.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 1.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": False, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": True, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    
    # ==========================================
    # CLEAN ARCHITECTURE TESTS (6 cases)
    # ==========================================
    {
        "name": "19. CLEAN - Outer Depends on Inner (Controller -> Entity)",
        "payload": {
            "architecture_pattern": "clean_architecture",
            "architecture_confidence": 0.72,
            "loc": 102.0, "methods": 5.0, "classes": 1.0, "avg_cc": 2.0,
            "imports": 14.0, "annotations": 9.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "outer_depends_on_inner_clean"
    },
    {
        "name": "20. CLEAN - UseCase Framework Coupling",
        "payload": {
            "architecture_pattern": "clean_architecture",
            "architecture_confidence": 0.68,
            "loc": 125.0, "methods": 6.0, "classes": 1.0, "avg_cc": 2.2,
            "imports": 18.0, "annotations": 12.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 1.0, "gateway_deps": 1.0, "total_cross_layer_deps": 2.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "usecase_framework_coupling_clean"
    },
    {
        "name": "21. CLEAN - Entity Framework Coupling",
        "payload": {
            "architecture_pattern": "clean_architecture",
            "architecture_confidence": 0.75,
            "loc": 65.0, "methods": 2.0, "classes": 1.0, "avg_cc": 1.2,
            "imports": 12.0, "annotations": 10.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 0.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "entity_framework_coupling_clean"
    },
    {
        "name": "22. CLEAN - Missing Gateway Interface",
        "payload": {
            "architecture_pattern": "clean_architecture",
            "architecture_confidence": 0.70,
            "loc": 140.0, "methods": 5.0, "classes": 1.0, "avg_cc": 2.1,
            "imports": 16.0, "annotations": 8.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 2.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "missing_gateway_interface_clean"
    },
    {
        "name": "23. CLEAN - Proper UseCase Implementation",
        "payload": {
            "architecture_pattern": "clean_architecture",
            "architecture_confidence": 0.77,
            "loc": 115.0, "methods": 5.0, "classes": 1.0, "avg_cc": 1.9,
            "imports": 10.0, "annotations": 4.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 2.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    {
        "name": "24. CLEAN - Proper Controller Layer",
        "payload": {
            "architecture_pattern": "clean_architecture",
            "architecture_confidence": 0.74,
            "loc": 85.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.4,
            "imports": 9.0, "annotations": 7.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 2.0, "gateway_deps": 0.0, "total_cross_layer_deps": 2.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": True, "has_validation": True,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    
    # ==========================================
    # COMMON ANTI-PATTERNS (6 cases)
    # ==========================================
    {
        "name": "25. COMMON - Broad Exception Catch (Service)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.90,
            "loc": 75.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.5,
            "imports": 8.0, "annotations": 5.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "broad_catch"
    },
    {
        "name": "26. COMMON - Broad Exception Catch (Controller)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.87,
            "loc": 95.0, "methods": 4.0, "classes": 1.0, "avg_cc": 1.8,
            "imports": 10.0, "annotations": 7.0,
            "controller_deps": 0.0, "service_deps": 2.0, "repository_deps": 0.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "broad_catch"
    },
    {
        "name": "27. COMMON - No Validation (POST endpoint)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.93,
            "loc": 68.0, "methods": 2.0, "classes": 1.0, "avg_cc": 1.3,
            "imports": 7.0, "annotations": 4.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 2.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "no_validation"
    },
    {
        "name": "28. COMMON - No Validation (PUT endpoint)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.91,
            "loc": 82.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.6,
            "imports": 9.0, "annotations": 5.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "no_validation"
    },
    {
        "name": "29. COMMON - Tight Coupling (new keyword in Service)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.87,
            "loc": 92.0, "methods": 4.0, "classes": 1.0, "avg_cc": 1.7,
            "imports": 10.0, "annotations": 6.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 1.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "tight_coupling_new_keyword"
    },
    {
        "name": "30. COMMON - Tight Coupling (new keyword in Controller)",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.89,
            "loc": 78.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.5,
            "imports": 8.0, "annotations": 5.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "tight_coupling_new_keyword"
    },
    
    # ==========================================
    # MVC ARCHITECTURE TESTS (3 cases)
    # ==========================================
    {
        "name": "31. MVC - Business Logic in Controller",
        "payload": {
            "architecture_pattern": "mvc",
            "architecture_confidence": 0.89,
            "loc": 135.0, "methods": 6.0, "classes": 1.0, "avg_cc": 2.4,
            "imports": 11.0, "annotations": 7.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": False,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "business_logic_in_controller_layered"
    },
    {
        "name": "32. MVC - Layer Skip",
        "payload": {
            "architecture_pattern": "mvc",
            "architecture_confidence": 0.85,
            "loc": 110.0, "methods": 5.0, "classes": 1.0, "avg_cc": 2.0,
            "imports": 13.0, "annotations": 9.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 2.0,
            "entity_deps": 1.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 3.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": True, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": True
        },
        "expected": "layer_skip_in_layered"
    },
    {
        "name": "33. MVC - Clean Implementation",
        "payload": {
            "architecture_pattern": "mvc",
            "architecture_confidence": 0.92,
            "loc": 70.0, "methods": 3.0, "classes": 1.0, "avg_cc": 1.3,
            "imports": 8.0, "annotations": 6.0,
            "controller_deps": 0.0, "service_deps": 1.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 1.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": True, "has_validation": True,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    },
    
    # ==========================================
    # EDGE CASES (2 cases)
    # ==========================================
    {
        "name": "34. EDGE - Large Complex File",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.94,
            "loc": 450.0, "methods": 15.0, "classes": 2.0, "avg_cc": 4.5,
            "imports": 35.0, "annotations": 22.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 3.0,
            "entity_deps": 2.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 5.0,
            "has_business_logic": True, "has_data_access": True,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "missing_transaction_in_layered"
    },
    {
        "name": "35. EDGE - Minimal Entity Class",
        "payload": {
            "architecture_pattern": "layered",
            "architecture_confidence": 0.88,
            "loc": 28.0, "methods": 0.0, "classes": 1.0, "avg_cc": 1.0,
            "imports": 3.0, "annotations": 6.0,
            "controller_deps": 0.0, "service_deps": 0.0, "repository_deps": 0.0,
            "entity_deps": 0.0, "adapter_deps": 0.0, "port_deps": 0.0,
            "usecase_deps": 0.0, "gateway_deps": 0.0, "total_cross_layer_deps": 0.0,
            "has_business_logic": False, "has_data_access": False,
            "has_http_handling": False, "has_validation": False,
            "has_transaction": False, "violates_layer_separation": False
        },
        "expected": "clean"
    }
]

def run_tests():
    """Run all test cases and generate report"""
    
    print("="*80)
    print("SPRINGFORGE ANTI-PATTERN MODEL - AUTOMATED TESTING")
    print("="*80)
    print(f"\nStarting tests at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Endpoint: {API_URL}")
    print(f"Total test cases: {len(test_cases)}\n")
    
    results = []
    passed = 0
    failed = 0
    
    # Track anti-pattern coverage
    anti_pattern_coverage = {}
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/{len(test_cases)}: {test['name']}")
        print(f"{'='*80}")
        
        try:
            # Make API request
            response = requests.post(API_URL, json=test['payload'], timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                predicted = result.get('anti_pattern', 'UNKNOWN')
                expected = test['expected']
                
                # Track coverage
                if expected not in anti_pattern_coverage:
                    anti_pattern_coverage[expected] = {'total': 0, 'passed': 0}
                anti_pattern_coverage[expected]['total'] += 1
                
                # Check if prediction matches expected
                status = "✅ PASS" if predicted == expected else "❌ FAIL"
                if predicted == expected:
                    passed += 1
                    anti_pattern_coverage[expected]['passed'] += 1
                else:
                    failed += 1
                
                print(f"Status: {status}")
                print(f"Expected: {expected}")
                print(f"Predicted: {predicted}")
                
                # Store result
                results.append({
                    'test_name': test['name'],
                    'expected': expected,
                    'predicted': predicted,
                    'status': 'PASS' if predicted == expected else 'FAIL',
                    'http_status': response.status_code
                })
                
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                failed += 1
                results.append({
                    'test_name': test['name'],
                    'expected': test['expected'],
                    'predicted': 'ERROR',
                    'status': 'ERROR',
                    'http_status': response.status_code
                })
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection Error: {str(e)}")
            failed += 1
            results.append({
                'test_name': test['name'],
                'expected': test['expected'],
                'predicted': 'CONNECTION_ERROR',
                'status': 'ERROR',
                'http_status': 0
            })
    
    # Generate summary report
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Tests: {len(test_cases)}")
    print(f"Passed: {passed} ({passed/len(test_cases)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(test_cases)*100:.1f}%)")
    print(f"Accuracy: {passed/len(test_cases)*100:.1f}%")
    
    # Print anti-pattern coverage
    print(f"\n{'='*80}")
    print("ANTI-PATTERN COVERAGE")
    print(f"{'='*80}")
    for pattern, stats in sorted(anti_pattern_coverage.items()):
        accuracy = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{pattern:50} | {stats['passed']}/{stats['total']} ({accuracy:.0f}%)")
    
    # Save detailed report
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("SPRINGFORGE ANTI-PATTERN MODEL - TEST REPORT\n")
        f.write("="*80 + "\n\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"API Endpoint: {API_URL}\n\n")
        
        f.write(f"SUMMARY:\n")
        f.write(f"Total Tests: {len(test_cases)}\n")
        f.write(f"Passed: {passed}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Accuracy: {passed/len(test_cases)*100:.1f}%\n\n")
        
        f.write("="*80 + "\n")
        f.write("ANTI-PATTERN COVERAGE:\n")
        f.write("="*80 + "\n\n")
        for pattern, stats in sorted(anti_pattern_coverage.items()):
            accuracy = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            f.write(f"{pattern:50} | {stats['passed']}/{stats['total']} ({accuracy:.0f}%)\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("DETAILED RESULTS:\n")
        f.write("="*80 + "\n\n")
        
        for i, result in enumerate(results, 1):
            f.write(f"{i}. {result['test_name']}\n")
            f.write(f"   Status: {result['status']}\n")
            f.write(f"   Expected: {result['expected']}\n")
            f.write(f"   Predicted: {result['predicted']}\n")
            f.write(f"   HTTP Status: {result['http_status']}\n\n")
    
    print(f"\n📄 Detailed report saved to: {OUTPUT_FILE}")
    print("="*80)
    
    return results

if __name__ == "__main__":
    try:
        results = run_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()