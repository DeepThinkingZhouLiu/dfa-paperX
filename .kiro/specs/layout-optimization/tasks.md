# Implementation Plan

- [x] 1. Enhance prompt templates with layout constraints
  - Add chunk design principles, grid complexity constraints, and aspect ratio constraints to prompts
  - _Requirements: 1.1, 1.2, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 1.1 Update Semantic Constructor prompt template
  - Add CHUNK_DESIGN_PRINCIPLES and NODE_DESIGN_PRINCIPLES to the prompt
  - Modify `prompts_repo.py` to include the new constraints in `p2g_semantic_constructor` prompts
  - _Requirements: 1.1, 1.2, 1.5, 4.1, 4.5_

- [x] 1.2 Update Chunk Layout Planner prompt template
  - Add GRID_COMPLEXITY_CONSTRAINTS and CHUNK_MERGE_RULES to the prompt
  - Modify `prompts_repo.py` to include the new constraints in `p2g_chunk_layout_planner` prompts
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.2_

- [x] 1.3 Update Node Layout Planner prompt template
  - Add ASPECT_RATIO_CONSTRAINTS and NODE_TYPE_SIZE_MAPPING to the prompt
  - Modify `prompts_repo.py` to include the new constraints in `p2g_node_layout_planner` prompts
  - _Requirements: 3.1, 3.2, 3.3, 4.3_

- [x] 1.4 Write property test for prompt constraint injection
  - **Property 1: Prompt contains required constraints**
  - **Validates: Requirements 4.1, 4.2, 4.3**

- [ ] 2. Implement layout validation module
  - Create LayoutValidator class with methods to validate chunk count, grid complexity, aspect ratios, and bbox boundaries
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 2.1 Create LayoutValidator class structure
  - Define the LayoutValidator class with validation methods
  - Create ValidationResult data model
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 2.2 Implement chunk count validation
  - Implement `validate_chunk_count` method to check if chunk count is between 3 and 7
  - _Requirements: 1.1, 7.1_

- [ ] 2.3 Write property test for chunk count validation
  - **Property 1: Chunk count constraint**
  - **Validates: Requirements 1.1**

- [ ] 2.4 Implement grid complexity validation
  - Implement `validate_grid_complexity` method to check grid dimensions and total cells
  - _Requirements: 2.1, 2.2, 2.3, 7.2_

- [ ] 2.5 Write property test for grid complexity validation
  - **Property 4: Grid complexity limit**
  - **Validates: Requirements 2.3**

- [ ] 2.6 Implement aspect ratio validation
  - Implement `validate_node_aspect_ratios` method to check all node aspect ratios
  - _Requirements: 3.1, 3.2, 7.3, 7.4_

- [ ] 2.7 Write property test for aspect ratio validation
  - **Property 5: Node aspect ratio bounds**
  - **Validates: Requirements 3.1**

- [ ] 2.8 Implement bbox boundary validation
  - Implement `validate_bbox_boundaries` method to check canvas containment and no overlaps
  - _Requirements: 5.1, 5.2, 5.3, 7.5_

- [ ] 2.9 Write property test for bbox boundary validation
  - **Property 7: Bbox boundary containment**
  - **Property 8: No bbox overlaps**
  - **Property 9: Canvas boundary containment**
  - **Validates: Requirements 5.1, 5.2, 5.3**

- [ ] 3. Implement layout correction module
  - Create LayoutCorrector class with methods to automatically fix common layout issues
  - _Requirements: 1.2, 1.3, 3.2, 5.4_

- [ ] 3.1 Create LayoutCorrector class structure
  - Define the LayoutCorrector class with correction methods
  - _Requirements: 5.4_

- [ ] 3.2 Implement lightweight chunk merging
  - Implement `merge_lightweight_chunks` method to merge chunks with fewer than 4 nodes
  - _Requirements: 1.2_

- [ ] 3.3 Write property test for chunk merging
  - **Property 2: Lightweight chunk merging**
  - **Validates: Requirements 1.2**

- [ ] 3.4 Implement aspect ratio adjustment
  - Implement `adjust_extreme_aspect_ratios` method to fix nodes with extreme aspect ratios
  - _Requirements: 3.2_

- [ ] 3.5 Implement bbox overlap fixing
  - Implement `fix_bbox_overlaps` method to resolve overlapping bboxes
  - _Requirements: 5.2_

- [ ] 3.6 Implement connectivity enforcement
  - Implement `ensure_connectivity` method to ensure all nodes are within their parent chunk
  - _Requirements: 5.3_

- [ ] 3.7 Write unit tests for correction methods
  - Test each correction method with various edge cases
  - _Requirements: 1.2, 3.2, 5.2, 5.3_

- [ ] 4. Implement layout quality metrics module
  - Create LayoutQualityMetrics class to calculate and report layout quality indicators
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 4.1 Create LayoutQualityMetrics class
  - Define the class with methods for calculating various metrics
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 4.2 Implement basic metrics calculation
  - Implement methods for chunk count, grid dimensions, and average nodes per chunk
  - _Requirements: 7.1, 7.2, 7.5_

- [ ] 4.3 Implement aspect ratio distribution calculation
  - Implement `calculate_aspect_ratio_distribution` and `calculate_extreme_aspect_ratio_percentage`
  - _Requirements: 7.3, 7.4_

- [ ] 4.4 Implement quality report generation
  - Implement `generate_quality_report` to produce a comprehensive quality assessment
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 4.5 Write unit tests for metrics calculation
  - Test each metric calculation method with known inputs
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 5. Integrate validation and correction into agent pipeline
  - Modify agent classes to call validation and correction logic in their update_state_result methods
  - _Requirements: 5.4, 5.5_

- [ ] 5.1 Integrate validation into P2gSemanticConstructorAgent
  - Call LayoutValidator.validate_chunk_count after semantic_json generation
  - Trigger LayoutCorrector.merge_lightweight_chunks if validation fails
  - _Requirements: 1.1, 1.2, 5.4_

- [ ] 5.2 Integrate validation into P2gChunkLayoutPlannerAgent
  - Call LayoutValidator.validate_grid_complexity after layout_plan generation
  - Log warnings if validation fails (no automatic correction at this level)
  - _Requirements: 2.1, 2.2, 2.3, 5.4_

- [ ] 5.3 Integrate validation into P2gNodeLayoutPlannerAgent
  - Call LayoutValidator.validate_node_aspect_ratios after node_layout_plan generation
  - Trigger LayoutCorrector.adjust_extreme_aspect_ratios if validation fails
  - _Requirements: 3.1, 3.2, 5.4_

- [ ] 5.4 Integrate validation into P2gLayoutConstructorAgent
  - Call LayoutValidator.validate_bbox_boundaries after layout_json generation
  - Trigger LayoutCorrector.fix_bbox_overlaps and ensure_connectivity if validation fails
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 5.5 Write integration tests for validation pipeline
  - Test the complete validation and correction flow with various inputs
  - _Requirements: 5.4, 5.5_

- [ ] 6. Add quality metrics reporting
  - Integrate LayoutQualityMetrics into the pipeline to generate reports after layout generation
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 6.1 Add metrics calculation to pipeline
  - Call LayoutQualityMetrics.generate_quality_report at the end of layout generation
  - Store the report in state.agent_results
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 6.2 Create quality report visualization
  - Implement a function to format and display the quality report
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 6.3 Write unit tests for report generation
  - Test report generation with various layout configurations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. Implement node type-specific bbox sizing
  - Add logic to calculate appropriate bbox sizes based on node type and content
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 7.1 Create BboxSizeCalculator utility class
  - Define methods for calculating bbox sizes for different node types
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 7.2 Implement module box sizing
  - Implement logic to ensure module boxes have minimum dimensions of 150x100
  - _Requirements: 6.1_

- [ ] 7.3 Write property test for module box sizing
  - **Property 10: Module box minimum size**
  - **Validates: Requirements 6.1**

- [ ] 7.4 Implement annotation sizing
  - Implement logic to calculate annotation bbox based on text lines
  - _Requirements: 6.2_

- [ ] 7.5 Implement connector sizing
  - Implement logic to ensure connectors have aspect ratio between 3.0 and 10.0
  - _Requirements: 6.3_

- [ ] 7.6 Write property test for connector sizing
  - **Property 11: Connector aspect ratio**
  - **Validates: Requirements 6.3**

- [ ] 7.7 Implement complex visual content sizing
  - Implement logic to ensure complex content has minimum area of 20000 square pixels
  - _Requirements: 6.4_

- [ ] 7.8 Write property test for complex content sizing
  - **Property 12: Complex visual content area**
  - **Validates: Requirements 6.4**

- [ ] 7.9 Integrate BboxSizeCalculator into Node Layout Planner
  - Modify P2gNodeLayoutPlannerAgent to use BboxSizeCalculator
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. End-to-end testing and validation
  - Test the complete optimized pipeline with real-world examples
  - _Requirements: All_

- [ ] 9.1 Run regression tests
  - Execute existing test cases (e.g., test_p2g_layout_pipeline.py) with the optimized system
  - Compare results with baseline
  - _Requirements: All_

- [ ] 9.2 Test with the problematic example
  - Run the pipeline with the user's original problematic example (5x3 grid, 9 chunks, 42 nodes)
  - Verify that the optimized system produces better results
  - _Requirements: All_

- [ ] 9.3 Generate quality comparison report
  - Compare layout quality metrics before and after optimization
  - Document improvements in chunk count, grid complexity, and aspect ratios
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 9.4 Write end-to-end integration tests
  - Test complete pipeline with various user targets
  - Verify all constraints are satisfied
  - _Requirements: All_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
