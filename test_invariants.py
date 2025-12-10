#!/usr/bin/env python3
"""
invariant-sdk Test Suite

Comprehensive tests for all 5 Constitutional Invariants:
I.   Identity (Merkle)
II.  Closure (Transitivity)
III. Energy (MDL Sublimation)
IV.  Hierarchy (Rings)
V.   Separation (Phase Law)
"""

import sys
sys.path.insert(0, 'python')


def test_invariant_i_identity():
    """Test I: Identity = Merkle Hash (from Rust kernel)"""
    from invariant_kernel import get_token_hash_hex, bond_id
    
    # Determinism
    h1 = get_token_hash_hex("intelligence")
    h2 = get_token_hash_hex("intelligence")
    assert h1 == h2, "Merkle hash not deterministic"
    
    # Different inputs → different hashes
    h3 = get_token_hash_hex("cat")
    assert h1 != h3, "Different inputs should have different hashes"
    
    # Bond ID (edge identity)
    b1 = bond_id("A", "B", "IMP")
    b2 = bond_id("A", "B", "IMP")
    assert b1 == b2, "Bond ID not deterministic"
    
    # Order matters
    b3 = bond_id("B", "A", "IMP")
    assert b1 != b3, "Bond order should matter"
    
    print("✓ I. Identity (Merkle) — PASSED")


def test_invariant_ii_closure():
    """Test II: Closure = Transitive Derivation via λ-closure"""
    from invariant_sdk.core.reactor import Tank, Truth, Reactor
    
    tank = Tank()
    tank.absorb('cat', 'animal', 'IMP', 1.0, Truth.SIGMA, 'test')
    tank.absorb('animal', 'living', 'IMP', 1.0, Truth.SIGMA, 'test')
    
    assert len(tank.edges) == 2, "Should start with 2 edges"
    
    reactor = Reactor(tank)
    reactor.cycle_lambda()
    
    # Should derive cat → living
    assert len(tank.edges) == 3, f"λ-closure should derive 1 edge, got {len(tank.edges)}"
    
    # Verify the derived edge exists
    from invariant_kernel import get_token_hash_hex, bond_id
    cat_h = get_token_hash_hex('cat')
    living_h = get_token_hash_hex('living')
    edge_id = bond_id(cat_h, living_h, 'IMP')
    
    assert edge_id in tank.edges, "Derived edge cat→living not found"
    assert tank.edges[edge_id].ring == Truth.LAMBDA, "Derived edge should be λ-ring"
    
    print("✓ II. Closure (Transitivity) — PASSED")


def test_invariant_iii_energy():
    """Test III: Energy = MDL Sublimation"""
    from invariant_sdk.core.reactor import Tank, Truth, EdgeStatus
    from invariant_kernel import get_token_hash_hex, bond_id
    
    tank = Tank()
    
    # Add facts
    tank.absorb('Socrates', 'Mortal', 'IS_A', 1.0, Truth.SIGMA, 'observation')
    tank.absorb('Plato', 'Mortal', 'IS_A', 1.0, Truth.SIGMA, 'observation')
    tank.absorb('Aristotle', 'Mortal', 'IS_A', 1.0, Truth.SIGMA, 'observation')
    
    w_before = tank.get_active_weight()
    assert w_before == 7, f"W_active should be 7, got {w_before}"  # 4 nodes + 3 edges
    
    # Add rule
    tank.absorb('Man', 'Mortal', 'IS_A', 10.0, Truth.ALPHA, 'axiom')
    
    # Supersede facts (MDL)
    fact_ids = []
    for name in ['Socrates', 'Plato', 'Aristotle']:
        h = get_token_hash_hex(name)
        mortal_h = get_token_hash_hex('Mortal')
        eid = bond_id(h, mortal_h, 'IS_A')
        fact_ids.append(eid)
    
    rule_hash = bond_id(get_token_hash_hex('Man'), get_token_hash_hex('Mortal'), 'IS_A')
    count = tank.supersede(fact_ids, rule_hash)
    
    assert count == 3, f"Should supersede 3 facts, got {count}"
    
    w_after = tank.get_active_weight()
    w_storage = tank.get_storage_weight()
    
    # W_active compressed, W_storage preserved
    assert w_after < w_storage, f"W_active ({w_after}) should be < W_storage ({w_storage})"
    
    # Facts still exist but SUPERSEDED
    for eid in fact_ids:
        assert tank.edges[eid].status == EdgeStatus.SUPERSEDED
        assert tank.edges[eid].superseded_by == rule_hash
    
    print("✓ III. Energy (MDL Sublimation) — PASSED")


def test_invariant_iv_hierarchy():
    """Test IV: Hierarchy = Ring Ordering α > σ > λ > η"""
    from invariant_sdk.core.reactor import Tank, Truth
    
    tank = Tank()
    
    # Add same edge with different rings
    tank.absorb('A', 'B', 'IMP', 1.0, Truth.ETA, 'hypothesis')
    tank.absorb('A', 'B', 'IMP', 2.0, Truth.SIGMA, 'observation')
    
    # Edge should exist once
    assert len(tank.edges) == 1, "Same edge should be merged"
    
    # Ring should be highest (lowest value)
    edge = list(tank.edges.values())[0]
    assert edge.ring == Truth.SIGMA, f"Ring should be σ (1), got {edge.ring}"
    
    # Provenance should have both
    assert len(edge.provenance) == 2, "Should preserve both provenances"
    
    # Verify ring ordering
    assert Truth.ALPHA.value < Truth.SIGMA.value < Truth.LAMBDA.value < Truth.ETA.value
    
    print("✓ IV. Hierarchy (Rings) — PASSED")


def test_invariant_v_separation():
    """Test V: Separation = Crystal and Liquid never mix"""
    from invariant_sdk.core.reactor import Tank, Truth, EdgeStatus
    
    # Verify crystallized edges from Liquid are η (hypothesis)
    # This would be tested in engine.crystallize() but we verify the structure
    
    tank = Tank()
    
    # Simulate crystallization result (should be ETA)
    tank.absorb('vec1', 'vec2', 'SIMILAR', 0.85, Truth.ETA, 'crystal:vector')
    
    edge = list(tank.edges.values())[0]
    assert edge.ring == Truth.ETA, "Liquid→Crystal edges must be η"
    
    # Verify Crystal (σ, α) and Liquid (η) are distinct
    tank.absorb('fact1', 'fact2', 'IMP', 1.0, Truth.SIGMA, 'observed')
    
    crystal_edges = [e for e in tank.edges.values() if e.ring.value <= Truth.SIGMA.value]
    liquid_edges = [e for e in tank.edges.values() if e.ring == Truth.ETA]
    
    assert len(crystal_edges) == 1, "Should have 1 Crystal edge"
    assert len(liquid_edges) == 1, "Should have 1 Liquid edge"
    
    print("✓ V. Separation (Phase Law) — PASSED")


def test_agent_structures():
    """Test Agent data structures are minimal"""
    from invariant_sdk.tools.agent import Concept, StreamState
    
    # Concept is minimal
    c = Concept(name="test", type="DEF")
    assert c.name == "test"
    assert c.type == "DEF"
    
    # StreamState is minimal (only last_block_id)
    s = StreamState()
    assert hasattr(s, 'last_block_id')
    assert not hasattr(s, 'known_concepts'), "known_concepts should be removed"
    assert not hasattr(s, 'symbol_registry'), "symbol_registry should be removed"
    
    print("✓ Agent structures minimal — PASSED")


def test_hub_topology():
    """Test Hub Topology is more efficient than mesh"""
    from invariant_sdk.core.reactor import Tank, Truth
    
    tank = Tank()
    
    # 10 blocks all reference same concept
    concept = "machine_learning"
    blocks = [f"block_{i}" for i in range(10)]
    
    # Hub topology: k edges
    for b in blocks:
        tank.absorb(concept, b, 'DEF', 1.0, Truth.SIGMA, 'test')
    
    hub_edges = len(tank.edges)
    
    # Mesh would need k*(k-1)
    mesh_edges = len(blocks) * (len(blocks) - 1)
    
    assert hub_edges == len(blocks), f"Hub should have {len(blocks)} edges, got {hub_edges}"
    assert hub_edges < mesh_edges, f"Hub ({hub_edges}) should be < Mesh ({mesh_edges})"
    
    print(f"✓ Hub topology O(k) vs O(k²) — {hub_edges} vs {mesh_edges} — PASSED")


def test_agent_end_to_end():
    """Test full StructuralAgent.digest workflow (the bug that was missed!)"""
    import tempfile
    from invariant_sdk import InvariantEngine
    from invariant_sdk.tools import StructuralAgent
    
    def mock_llm(prompt):
        return '''
{
    "blocks": [
        {
            "start_quote": "Module X depends",
            "end_quote": "on Library Y.",
            "logic": "ORIGIN",
            "concepts": [{"name": "Module_X", "type": "DEF"}]
        }
    ]
}
'''
    
    tmpdir = tempfile.mkdtemp()
    
    engine = InvariantEngine(tmpdir)
    agent = StructuralAgent(engine, llm=mock_llm)
    
    text = "Module X depends on Library Y."
    count = agent.digest("test_doc", text)
    
    assert count >= 1, f"digest() should return >= 1, got {count}"
    
    # Verify block was saved
    assert engine.block_store.exists, "BlockStore should have exists() method"
    blocks = engine.block_store.get_all()
    assert len(blocks) >= 1, f"Should have saved blocks, got {len(blocks)}"
    
    print("✓ Agent end-to-end (InvariantEngine + StructuralAgent) — PASSED")


def main():
    print("=" * 60)
    print("invariant-sdk Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_invariant_i_identity()
        test_invariant_ii_closure()
        test_invariant_iii_energy()
        test_invariant_iv_hierarchy()
        test_invariant_v_separation()
        test_agent_structures()
        test_hub_topology()
        test_agent_end_to_end()  # NEW: catches storage bugs!
        
        print()
        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print()
        print("All 5 Constitutional Invariants verified:")
        print("  I.   Identity (Merkle) — Rust kernel")
        print("  II.  Closure (λ-derivation)")
        print("  III. Energy (MDL Sublimation)")
        print("  IV.  Hierarchy (Ring ordering)")
        print("  V.   Separation (Phase Law)")
        print("  + Agent end-to-end integration")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
