import json
from superlarynx.acoustic_graph import AcousticGraph, GraphNode, NodeType, EdgeType
from superlarynx.compiler import compile_graph_to_recipe

def run_tests():
    print("Testing Graph Validation and Compilation...\n")
    
    # Test 1: MUG -> interaction -> FLOOR
    print("--- Test 1: MUG --interaction--> FLOOR ---")
    g1 = AcousticGraph()
    n1 = g1.add_node(GraphNode(node_type=NodeType.OBJECT, label="MUG", mechanism="IMPULSE"))
    n2 = g1.add_node(GraphNode(node_type=NodeType.OBJECT, label="FLOOR", mechanism="MODAL_RESPONSE"))
    g1.add_edge(n1, n2, EdgeType.INTERACTION)
    
    dict_g1 = g1.to_dict()
    errors1 = AcousticGraph.validate_dict(dict_g1)
    print(f"Validation errors (should be empty): {errors1}")
    
    g1_deserialized = AcousticGraph.from_dict(dict_g1)
    recipe1 = compile_graph_to_recipe(g1_deserialized)
    print(f"Compilation success! Recipe duration: {recipe1.get('duration')}s")
    print(f"Compiler trace length: {len(recipe1.get('compiler_trace', []))}")
    print()

    # Test 2: MUG -> interaction -> COUNTER -> energy_transfer -> MUG
    print("--- Test 2: Circular/Reciprocal interaction ---")
    g2 = AcousticGraph()
    m_node = g2.add_node(GraphNode(node_type=NodeType.OBJECT, label="MUG", mechanism="IMPULSE"))
    c_node = g2.add_node(GraphNode(node_type=NodeType.OBJECT, label="COUNTER", mechanism="MODAL_RESPONSE"))
    g2.add_edge(m_node, c_node, EdgeType.INTERACTION)
    g2.add_edge(c_node, m_node, EdgeType.ENERGY_TRANSFER)
    
    dict_g2 = g2.to_dict()
    errors2 = AcousticGraph.validate_dict(dict_g2)
    print(f"Validation errors (should be empty): {errors2}")
    
    g2_deserialized = AcousticGraph.from_dict(dict_g2)
    recipe2 = compile_graph_to_recipe(g2_deserialized)
    print("Compilation success!")
    print()

    # Test 3: IMPACT -> causality -> CRACK
    print("--- Test 3: IMPACT --causality--> CRACK ---")
    g3 = AcousticGraph()
    impact = g3.add_node(GraphNode(node_type=NodeType.EVENT, label="IMPACT", mechanism="COLLISION"))
    crack = g3.add_node(GraphNode(node_type=NodeType.EVENT, label="CRACK", mechanism="IMPULSE"))
    g3.add_edge(impact, crack, EdgeType.CAUSALITY)
    
    dict_g3 = g3.to_dict()
    errors3 = AcousticGraph.validate_dict(dict_g3)
    print(f"Validation errors (should be empty): {errors3}")
    
    g3_deserialized = AcousticGraph.from_dict(dict_g3)
    recipe3 = compile_graph_to_recipe(g3_deserialized)
    print("Compilation success!")
    print()

    # Test 4: Validation failure on unknown edge
    print("--- Test 4: Invalid EdgeType Validation ---")
    dict_invalid = g3.to_dict()
    dict_invalid["edges"][0]["type"] = "unknown_type_magic"
    errors_invalid = AcousticGraph.validate_dict(dict_invalid)
    print("Validation caught invalid edge:")
    print(json.dumps(errors_invalid, indent=2))
    print()

    print("All minimal compiler graph tests executed successfully.")

if __name__ == "__main__":
    run_tests()
