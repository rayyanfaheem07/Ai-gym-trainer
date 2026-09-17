import numpy as np

from ai.classifier.features import KEY_LANDMARK_INDICES, PoseFeatureExtractor
from ai.classifier.synthetic import BiomechanicalDataGenerator


def test_feature_extractor_frame_dimension():
    extractor = PoseFeatureExtractor()
    base_lm = BiomechanicalDataGenerator._create_base_skeleton("standing")
    feat = extractor.extract_frame_features(base_lm)

    assert isinstance(feat, np.ndarray)
    assert feat.ndim == 1
    assert len(feat) == len(extractor.feature_names_per_frame)
    assert not np.isnan(feat).any()
    assert not np.isinf(feat).any()


def test_feature_extractor_window_statistics():
    extractor = PoseFeatureExtractor()
    traj = BiomechanicalDataGenerator.generate_exercise_trajectory("squat", num_frames=30)
    win_feat = extractor.extract_window_features(traj)

    assert isinstance(win_feat, np.ndarray)
    assert win_feat.ndim == 1
    expected_dim = len(extractor.get_feature_names())
    assert len(win_feat) == expected_dim
    assert not np.isnan(win_feat).any()


def test_feature_extractor_edge_cases():
    extractor = PoseFeatureExtractor()

    # Empty window
    empty_feat = extractor.extract_window_features([])
    assert len(empty_feat) == len(extractor.get_feature_names())
    assert (empty_feat == 0).all()

    # Single frame window
    single_frame = BiomechanicalDataGenerator._create_base_skeleton("standing")[np.newaxis, ...]
    s_feat = extractor.extract_window_features(single_frame)
    assert len(s_feat) == len(extractor.get_feature_names())
    assert not np.isnan(s_feat).any()

    # Incomplete/corrupt landmarks
    corrupt_lm = np.zeros((10, 4), dtype=np.float32)
    c_feat = extractor.extract_frame_features(corrupt_lm)
    assert (c_feat == 0).all()


def test_feature_extractor_translation_and_scale_invariance():
    extractor = PoseFeatureExtractor()
    base_lm = BiomechanicalDataGenerator._create_base_skeleton("standing")

    # Shift skeleton by (dx, dy) and scale by 1.5x
    shifted_scaled = base_lm.copy()
    shifted_scaled[:, :2] = (shifted_scaled[:, :2] * 1.5) + np.array([0.3, -0.2])

    feat_orig = extractor.extract_frame_features(base_lm)
    feat_shifted = extractor.extract_frame_features(shifted_scaled)

    # Angle features start after 3 * len(KEY_LANDMARK_INDICES)
    angle_offset = 3 * len(KEY_LANDMARK_INDICES)
    # Angles should remain nearly identical under uniform translation & scale
    np.testing.assert_allclose(
        feat_orig[angle_offset : angle_offset + 10],
        feat_shifted[angle_offset : angle_offset + 10],
        atol=1e-3,
    )
