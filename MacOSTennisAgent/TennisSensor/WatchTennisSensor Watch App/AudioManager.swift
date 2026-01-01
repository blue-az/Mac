//
//  AudioManager.swift
//  WatchTennisSensor Watch App
//
//  Manages audio recording during tennis sessions
//

import Foundation
import AVFoundation
import WatchConnectivity

/// Manages microphone recording and audio file transfer
class AudioManager: NSObject, ObservableObject {

    // MARK: - Properties

    private var audioRecorder: AVAudioRecorder?
    private var audioSession: AVAudioSession?
    private var currentRecordingURL: URL?

    @Published var isRecording = false
    @Published var hasPermission = false
    @Published var recordingDuration: TimeInterval = 0

    private var durationTimer: Timer?

    // MARK: - Audio Settings

    /// Audio format settings optimized for voice on watchOS
    private var recordingSettings: [String: Any] {
        return [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000.0,           // 16kHz - sufficient for voice
            AVNumberOfChannelsKey: 1,            // Mono
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue,
            AVEncoderBitRateKey: 32000           // 32kbps
        ]
    }

    // MARK: - Initialization

    override init() {
        super.init()
        setupAudioSession()
        checkPermission()
    }

    // MARK: - Audio Session

    private func setupAudioSession() {
        audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession?.setCategory(.record, mode: .default)
            try audioSession?.setActive(true)
            print("🎤 Audio session configured")
        } catch {
            print("❌ Audio session setup failed: \(error.localizedDescription)")
        }
    }

    // MARK: - Permission

    func checkPermission() {
        switch AVAudioSession.sharedInstance().recordPermission {
        case .granted:
            hasPermission = true
            print("🎤 Microphone permission granted")
        case .denied:
            hasPermission = false
            print("🎤 Microphone permission denied")
        case .undetermined:
            hasPermission = false
            print("🎤 Microphone permission undetermined")
        @unknown default:
            hasPermission = false
        }
    }

    func requestPermission(completion: @escaping (Bool) -> Void) {
        AVAudioSession.sharedInstance().requestRecordPermission { [weak self] granted in
            DispatchQueue.main.async {
                self?.hasPermission = granted
                if granted {
                    print("✅ Microphone permission granted")
                } else {
                    print("❌ Microphone permission denied")
                }
                completion(granted)
            }
        }
    }

    // MARK: - Recording Control

    func startRecording(sessionId: String) {
        guard hasPermission else {
            print("❌ Cannot record: no microphone permission")
            requestPermission { [weak self] granted in
                if granted {
                    self?.startRecording(sessionId: sessionId)
                }
            }
            return
        }

        // Create unique file URL for this session
        let fileName = "audio_\(sessionId).m4a"
        let tempDir = FileManager.default.temporaryDirectory
        currentRecordingURL = tempDir.appendingPathComponent(fileName)

        guard let url = currentRecordingURL else {
            print("❌ Failed to create recording URL")
            return
        }

        // Remove existing file if present
        try? FileManager.default.removeItem(at: url)

        do {
            audioRecorder = try AVAudioRecorder(url: url, settings: recordingSettings)
            audioRecorder?.delegate = self
            audioRecorder?.prepareToRecord()

            if audioRecorder?.record() == true {
                isRecording = true
                recordingDuration = 0
                startDurationTimer()
                print("🎤 Audio recording started: \(fileName)")
            } else {
                print("❌ Failed to start audio recording")
            }
        } catch {
            print("❌ Audio recorder setup failed: \(error.localizedDescription)")
        }
    }

    func stopRecording() -> URL? {
        guard isRecording, let recorder = audioRecorder else {
            return nil
        }

        recorder.stop()
        isRecording = false
        stopDurationTimer()

        let url = currentRecordingURL
        print("🎤 Audio recording stopped. Duration: \(String(format: "%.1f", recordingDuration))s")

        if let url = url {
            let fileSize = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
            print("🎤 Audio file size: \(fileSize / 1024) KB")
        }

        return url
    }

    // MARK: - File Transfer

    func transferAudioFile(sessionId: String) {
        guard let url = currentRecordingURL,
              FileManager.default.fileExists(atPath: url.path) else {
            print("⚠️ No audio file to transfer")
            return
        }

        let session = WCSession.default
        guard session.activationState == .activated else {
            print("❌ WCSession not activated, cannot transfer audio")
            return
        }

        let metadata: [String: Any] = [
            "type": "audio_file",
            "session_id": sessionId,
            "duration": recordingDuration,
            "timestamp": Date().timeIntervalSince1970
        ]

        session.transferFile(url, metadata: metadata)
        print("📤 Audio file queued for transfer: \(url.lastPathComponent)")
    }

    // MARK: - Cleanup

    func cleanupRecording() {
        if let url = currentRecordingURL {
            try? FileManager.default.removeItem(at: url)
            print("🗑️ Audio file cleaned up")
        }
        currentRecordingURL = nil
        audioRecorder = nil
    }

    // MARK: - Duration Timer

    private func startDurationTimer() {
        durationTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let self = self, let recorder = self.audioRecorder else { return }
            DispatchQueue.main.async {
                self.recordingDuration = recorder.currentTime
            }
        }
    }

    private func stopDurationTimer() {
        durationTimer?.invalidate()
        durationTimer = nil
    }
}

// MARK: - AVAudioRecorderDelegate

extension AudioManager: AVAudioRecorderDelegate {
    func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        if flag {
            print("✅ Audio recording finished successfully")
        } else {
            print("❌ Audio recording finished with error")
        }
    }

    func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        if let error = error {
            print("❌ Audio encoding error: \(error.localizedDescription)")
        }
    }
}
