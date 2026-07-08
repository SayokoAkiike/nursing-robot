"""Tests for vision/qr_detection/demo/synthetic_frames.py."""
import cv2

from vision.qr_detection.demo.synthetic_frames import SceneConfig, generate_frames


def test_frame_count_matches_config():
    config = SceneConfig(seconds_per_code=1.0, fps=10)
    frames = list(generate_frames(config))
    assert len(frames) == config.total_frames == 20


def test_frames_have_expected_shape_and_dtype():
    config = SceneConfig(seconds_per_code=0.5, fps=8, frame_size=240)
    for frame, _info in generate_frames(config):
        assert frame.shape == (240, 240, 3)
        assert frame.dtype.name == "uint8"


def test_phase_labels_and_values_are_correct():
    config = SceneConfig(
        seconds_per_code=0.5, fps=10, patient_id="PATIENT_X", kit_id="KIT_Y"
    )
    infos = [info for _frame, info in generate_frames(config)]
    n = config.frames_per_code
    assert all(i.phase == "patient" and i.qr_value == "PATIENT_X" for i in infos[:n])
    assert all(i.phase == "kit" and i.qr_value == "KIT_Y" for i in infos[n:])


def test_box_size_grows_over_each_phase_simulating_approach():
    config = SceneConfig(seconds_per_code=1.0, fps=10, min_box_size=3, max_box_size=14)
    infos = [info for _frame, info in generate_frames(config)]
    n = config.frames_per_code
    patient_sizes = [i.box_size for i in infos[:n]]
    kit_sizes = [i.box_size for i in infos[n:]]
    assert patient_sizes[0] == config.min_box_size
    assert patient_sizes[-1] == config.max_box_size
    assert kit_sizes[0] == config.min_box_size
    assert kit_sizes[-1] == config.max_box_size


def test_generation_is_deterministic_for_a_given_seed():
    config_a = SceneConfig(seconds_per_code=0.5, fps=10, seed=42)
    config_b = SceneConfig(seconds_per_code=0.5, fps=10, seed=42)
    frames_a = [f for f, _ in generate_frames(config_a)]
    frames_b = [f for f, _ in generate_frames(config_b)]
    assert all((fa == fb).all() for fa, fb in zip(frames_a, frames_b))


def test_different_seeds_produce_different_occlusion_patterns():
    config_a = SceneConfig(seconds_per_code=1.0, fps=15, seed=1, occlusion_fraction=0.5)
    config_b = SceneConfig(seconds_per_code=1.0, fps=15, seed=2, occlusion_fraction=0.5)
    occluded_a = [info.occluded for _f, info in generate_frames(config_a)]
    occluded_b = [info.occluded for _f, info in generate_frames(config_b)]
    assert occluded_a != occluded_b


def test_final_frames_of_each_phase_are_actually_decodable():
    """Sanity check: this isn't just noise -- near the end of each phase
    (QR large, closest to camera) a real QR decoder must be able to read
    the correct value on at least one of the last few non-occluded
    frames."""
    config = SceneConfig(seconds_per_code=2.0, fps=15, seed=7)
    detector = cv2.QRCodeDetector()
    infos_and_frames = list(generate_frames(config))
    n = config.frames_per_code

    for phase_slice, expected_value in (
        (infos_and_frames[:n], config.patient_id),
        (infos_and_frames[n:], config.kit_id),
    ):
        decoded_values = set()
        for frame, info in phase_slice[-8:]:
            if info.occluded:
                continue
            data, _points, _ = detector.detectAndDecode(frame)
            if data:
                decoded_values.add(data)
        assert expected_value in decoded_values


def test_occlusion_fraction_zero_means_never_occluded():
    config = SceneConfig(seconds_per_code=1.0, fps=15, occlusion_fraction=0.0)
    infos = [info for _f, info in generate_frames(config)]
    assert not any(i.occluded for i in infos)
