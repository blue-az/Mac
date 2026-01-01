//
//  SettingsManager.swift
//  WatchTennisSensor Watch App
//
//  Manages user preferences for the Watch app
//

import Foundation
import Combine

/// Manages user settings with UserDefaults persistence
class SettingsManager: ObservableObject {

    // MARK: - Keys

    private enum Keys {
        static let isAudioEnabled = "isAudioEnabled"
    }

    // MARK: - Published Properties

    /// Whether audio recording is enabled during sessions
    @Published var isAudioEnabled: Bool {
        didSet {
            UserDefaults.standard.set(isAudioEnabled, forKey: Keys.isAudioEnabled)
            print("🎤 Audio recording \(isAudioEnabled ? "enabled" : "disabled")")
        }
    }

    // MARK: - Singleton

    static let shared = SettingsManager()

    // MARK: - Initialization

    init() {
        // Load saved setting, default to false (audio off)
        self.isAudioEnabled = UserDefaults.standard.bool(forKey: Keys.isAudioEnabled)
    }
}
