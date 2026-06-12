import Foundation

struct GolfSensorSample: Codable {
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
    let heartRate: Double?

    func toDictionary() -> [String: Any] {
        var dict: [String: Any] = [
            "timestamp": timestamp,
            "rotationRateX": rotationRateX,
            "rotationRateY": rotationRateY,
            "rotationRateZ": rotationRateZ,
            "gravityX": gravityX,
            "gravityY": gravityY,
            "gravityZ": gravityZ,
            "accelerationX": accelerationX,
            "accelerationY": accelerationY,
            "accelerationZ": accelerationZ,
            "quaternionW": quaternionW,
            "quaternionX": quaternionX,
            "quaternionY": quaternionY,
            "quaternionZ": quaternionZ
        ]
        if let hr = heartRate {
            dict["heartRate"] = hr
        }
        return dict
    }
}

struct GolfSwingMetrics: Codable {
    let timestamp: String
    let swing_id: String
    let metrics: Metrics
    let flags: Flags

    struct Metrics: Codable {
        let score: Double
        let impact_speed_mph: Double
        let hand_speed_mph: Double
        let readiness_pct: Double
        let hr_bpm: Int
    }

    struct Flags: Codable {
        let micro_fatigue: Bool
        let oracle_grounded: Bool
    }
}
