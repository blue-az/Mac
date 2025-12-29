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

class WorkoutManager: NSObject, ObservableObject {
    // MARK: - Properties

    private let healthStore = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?

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
                    return
                }

                Task { @MainActor in
                    self.isWorkoutActive = true
                    print("✅ Workout session started successfully")
                    print("   App will continue running even when screen goes dark")
                }
            }

        } catch {
            print("❌ Error starting workout: \(error.localizedDescription)")
        }
    }

    func stopWorkout() {
        guard let session = session else { return }

        // End the workout session
        session.end()

        print("🏁 Ending workout session...")
    }

    private func finishWorkout() {
        guard let builder = builder else { return }

        // Finish the workout
        builder.finishWorkout { [weak self] workout, error in
            guard let self = self else { return }

            if let error = error {
                print("❌ Error finishing workout: \(error.localizedDescription)")
                return
            }

            Task { @MainActor in
                self.isWorkoutActive = false
                self.session = nil
                self.builder = nil
                print("✅ Workout finished and saved to HealthKit")
            }
        }
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
