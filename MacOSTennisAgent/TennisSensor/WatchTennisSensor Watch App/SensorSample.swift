import Foundation

/// Sensor sample model matching the Python backend SensorSample
/// Represents a single IMU reading from Apple Watch CMMotionManager
struct SensorSampleSwift: Codable {
    let timestamp: Double
    let rotationRateX: Double
    let rotationRateY: Double
    let rotationRateZ: Double
    let gravityX: Double
    let gravityY: Double
    let gravityZ: Double
    let accelerationX: Double
    let accelerationY: Double
    let accelerationZ: Double
    let quaternionW: Double
    let quaternionX: Double
    let quaternionY: Double
    let quaternionZ: Double

    // Computed properties
    var rotationMagnitude: Double {
        sqrt(rotationRateX * rotationRateX +
             rotationRateY * rotationRateY +
             rotationRateZ * rotationRateZ)
    }

    var accelerationMagnitude: Double {
        sqrt(accelerationX * accelerationX +
             accelerationY * accelerationY +
             accelerationZ * accelerationZ)
    }
}

/// Session model
struct Session: Codable {
    let sessionId: String
    let device: String
    let date: String
    let startTime: Int
    var endTime: Int?
    var durationMinutes: Int?
    var shotCount: Int
    var metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case device
        case date
        case startTime = "start_time"
        case endTime = "end_time"
        case durationMinutes = "duration_minutes"
        case shotCount = "shot_count"
        case metadata
    }
}

/// Swing/Shot model
struct Swing: Codable {
    let shotId: String
    let sessionId: String
    let timestamp: Double
    let sequenceNumber: Int
    let rotationMagnitude: Double
    let accelerationMagnitude: Double
    var shotType: String?
    var spinType: String?
    var speedMph: Double?
    var power: Double?
    var consistency: Double?

    enum CodingKeys: String, CodingKey {
        case shotId = "shot_id"
        case sessionId = "session_id"
        case timestamp
        case sequenceNumber = "sequence_number"
        case rotationMagnitude = "rotation_magnitude"
        case accelerationMagnitude = "acceleration_magnitude"
        case shotType = "shot_type"
        case spinType = "spin_type"
        case speedMph = "speed_mph"
        case power
        case consistency
    }
}
