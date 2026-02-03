//
//  WorkoutManager.swift
//  WatchTennisSensor Watch App
//
//  Created for v2.6 to prevent screen sleep during recording
//  Uses HKWorkoutSession to keep app running when screen goes dark
//

import Foundation
import HealthKit
import Combine
import WatchKit

class WorkoutManager: NSObject, ObservableObject {
    // MARK: - Properties

    private let healthStore = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?
    private var runtimeSession: WKExtendedRuntimeSession?

    @Published @MainActor var isWorkoutActive = false
    @Published @MainActor var workoutState: HKWorkoutSessionState = .notStarted

    // MARK: - Initialization

    override init() {
        super.init()
        requestHealthKitAuthorization()
    }

    // MARK: - HealthKit Authorization

    private func requestHealthKitAuthorization() {
        let typesToShare: Set = [
            HKObjectType.workoutType()
        ]

        let typesToRead: Set = [
            HKObjectType.workoutType(),
            HKObjectType.quantityType(forIdentifier: .heartRate)!
        ]

        healthStore.requestAuthorization(toShare: typesToShare, read: typesToRead) { success, error in
            if let error = error {
                print("❌ HealthKit authorization error: \(error.localizedDescription)")
            } else {
                print("✅ HealthKit authorized")
            }
        }
    }

    // MARK: - Workout Session Control

    func startWorkout() {
        // Create workout configuration for tennis
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = .tennis
        configuration.locationType = .outdoor  // Can be changed to .indoor if needed
        DebugEventSender.send("workout_start_requested", details: ["activity": "tennis", "location": "outdoor"])

        startRuntimeSession()

        do {
            // Create workout session
            session = try HKWorkoutSession(healthStore: healthStore, configuration: configuration)
            builder = session?.associatedWorkoutBuilder()

            // Set up builder data source
            builder?.dataSource = HKLiveWorkoutDataSource(
                healthStore: healthStore,
                workoutConfiguration: configuration
            )

            // Assign delegates
            session?.delegate = self
            builder?.delegate = self

            // Start the workout session
            let startDate = Date()
            session?.startActivity(with: startDate)

            // Begin data collection
            builder?.beginCollection(withStart: startDate) { [weak self] success, error in
                guard let self = self else { return }

                if let error = error {
                    print("❌ Error beginning collection: \(error.localizedDescription)")
                    DebugEventSender.send(
                        "workout_collection_error",
                        details: ["error": error.localizedDescription]
                    )
                    return
                }

                Task { @MainActor in
                    self.isWorkoutActive = true
                    print("✅ Workout session started successfully")
                    print("   App will continue running even when screen goes dark")
                    DebugEventSender.send("workout_started")
                }
            }

        } catch {
            print("❌ Error starting workout: \(error.localizedDescription)")
            DebugEventSender.send("workout_start_error", details: ["error": error.localizedDescription])
        }
    }

    func stopWorkout() {
        guard let session = session else { return }

        // End the workout session
        session.end()

        print("🏁 Ending workout session...")
        DebugEventSender.send("workout_stop_requested")

        stopRuntimeSession()
    }

    private func finishWorkout() {
        guard let builder = builder else { return }

        // Finish the workout
        builder.finishWorkout { [weak self] workout, error in
            guard let self = self else { return }

            if let error = error {
                print("❌ Error finishing workout: \(error.localizedDescription)")
                DebugEventSender.send("workout_finish_error", details: ["error": error.localizedDescription])
                return
            }

            Task { @MainActor in
                self.isWorkoutActive = false
                self.session = nil
                self.builder = nil
                print("✅ Workout finished and saved to HealthKit")
                DebugEventSender.send("workout_finished")
                self.stopRuntimeSession()
            }
        }
    }

    // MARK: - Extended Runtime

    private func startRuntimeSession() {
        let runtime = WKExtendedRuntimeSession()
        runtime.delegate = self
        runtime.start()
        runtimeSession = runtime
        DebugEventSender.send("runtime_session_started")
    }

    private func stopRuntimeSession() {
        if let runtimeSession = runtimeSession {
            runtimeSession.invalidate()
        }
        runtimeSession = nil
    }
}

// MARK: - HKWorkoutSessionDelegate

extension WorkoutManager: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didChangeTo toState: HKWorkoutSessionState,
        from fromState: HKWorkoutSessionState,
        date: Date
    ) {
        Task { @MainActor in
            self.workoutState = toState

            print("🔄 Workout state changed: \(fromState.rawValue) -> \(toState.rawValue)")
            DebugEventSender.send(
                "workout_state_changed",
                details: ["from": fromState.rawValue, "to": toState.rawValue]
            )

            switch toState {
            case .running:
                self.isWorkoutActive = true
            case .ended:
                self.finishWorkout()
            default:
                break
            }
        }
    }

    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didFailWithError error: Error
    ) {
        print("❌ Workout session failed: \(error.localizedDescription)")
        DebugEventSender.send("workout_session_failed", details: ["error": error.localizedDescription])
    }
}

// MARK: - WKExtendedRuntimeSessionDelegate

extension WorkoutManager: WKExtendedRuntimeSessionDelegate {
    func extendedRuntimeSessionDidStart(_ extendedRuntimeSession: WKExtendedRuntimeSession) {
        DebugEventSender.send("runtime_session_did_start")
    }

    func extendedRuntimeSessionWillExpire(_ extendedRuntimeSession: WKExtendedRuntimeSession) {
        DebugEventSender.send("runtime_session_will_expire")
    }

    func extendedRuntimeSession(
        _ extendedRuntimeSession: WKExtendedRuntimeSession,
        didInvalidateWith reason: WKExtendedRuntimeSessionInvalidationReason,
        error: Error?
    ) {
        var details: [String: Any] = ["reason": reason.rawValue]
        if let error = error {
            details["error"] = error.localizedDescription
        }
        DebugEventSender.send("runtime_session_invalidated", details: details)
    }
}

// MARK: - HKLiveWorkoutBuilderDelegate

extension WorkoutManager: HKLiveWorkoutBuilderDelegate {
    nonisolated func workoutBuilder(
        _ workoutBuilder: HKLiveWorkoutBuilder,
        didCollectDataOf collectedTypes: Set<HKSampleType>
    ) {
        // Handle collected data (heart rate, calories, etc.)
        // This is called automatically by HealthKit
    }

    nonisolated func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {
        // Handle workout events
    }
}
