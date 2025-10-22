//! Protocol Version Registry
//!
//! Defines all BetaNet protocol versions, breaking changes, deprecation timelines,
//! and migration guides.

use super::protocol_version::ProtocolVersion;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Protocol version metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionMetadata {
    /// Protocol version
    pub version: ProtocolVersion,
    /// Release date
    pub release_date: String,
    /// End of life date (if deprecated)
    pub eol_date: Option<String>,
    /// Whether this version is deprecated
    pub deprecated: bool,
    /// Breaking changes in this version
    pub breaking_changes: Vec<String>,
    /// New features in this version
    pub features: Vec<String>,
    /// Migration guide URL or text
    pub migration_guide: Option<String>,
}

impl VersionMetadata {
    /// Create new version metadata
    pub fn new(version: ProtocolVersion, release_date: &str) -> Self {
        Self {
            version,
            release_date: release_date.to_string(),
            eol_date: None,
            deprecated: false,
            breaking_changes: Vec::new(),
            features: Vec::new(),
            migration_guide: None,
        }
    }

    /// Mark as deprecated with EOL date
    pub fn deprecate(mut self, eol_date: &str) -> Self {
        self.deprecated = true;
        self.eol_date = Some(eol_date.to_string());
        self
    }

    /// Add breaking change
    pub fn breaking_change(mut self, change: &str) -> Self {
        self.breaking_changes.push(change.to_string());
        self
    }

    /// Add feature
    pub fn feature(mut self, feature: &str) -> Self {
        self.features.push(feature.to_string());
        self
    }

    /// Set migration guide
    pub fn migration(mut self, guide: &str) -> Self {
        self.migration_guide = Some(guide.to_string());
        self
    }

    /// Check if version is end of life
    pub fn is_eol(&self) -> bool {
        if let Some(eol) = &self.eol_date {
            if let Ok(eol_datetime) = DateTime::parse_from_rfc3339(eol) {
                return Utc::now() > eol_datetime.with_timezone(&Utc);
            }
        }
        false
    }
}

/// Protocol version registry
pub struct VersionRegistry {
    versions: Vec<VersionMetadata>,
}

impl VersionRegistry {
    /// Create new version registry with all known versions
    pub fn new() -> Self {
        let mut registry = Self {
            versions: Vec::new(),
        };

        // Register all versions
        registry.register_v1_0_0();
        registry.register_v1_1_0();
        registry.register_v1_2_0();

        registry
    }

    /// Register v1.0.0 (baseline)
    fn register_v1_0_0(&mut self) {
        let metadata = VersionMetadata::new(
            ProtocolVersion::new(1, 0, 0),
            "2024-01-01T00:00:00Z",
        )
        .deprecate("2025-06-01T00:00:00Z")
        .feature("Basic Sphinx packet routing")
        .feature("Simple mixnet topology")
        .feature("Basic delay mechanisms")
        .migration(
            "To upgrade from v1.0.0:
1. Update node software to v1.1+ compatible version
2. Enable batch processing feature flag
3. Restart node to apply changes
4. Monitor for compatibility issues in logs",
        );

        self.versions.push(metadata);
    }

    /// Register v1.1.0 (batch processing)
    fn register_v1_1_0(&mut self) {
        let metadata = VersionMetadata::new(
            ProtocolVersion::new(1, 1, 0),
            "2024-06-01T00:00:00Z",
        )
        .feature("Batch packet processing for higher throughput")
        .feature("Improved pipeline architecture")
        .feature("Enhanced metrics and monitoring")
        .migration(
            "To upgrade from v1.1.0 to v1.2.0:
1. Update node software to v1.2+ compatible version
2. Enable relay lottery feature
3. Enable VRF delay mechanisms
4. Update packet format to include VRF fields
5. Restart node with new configuration
6. Verify VRF functionality in logs",
        );

        self.versions.push(metadata);
    }

    /// Register v1.2.0 (current - L4 privacy)
    fn register_v1_2_0(&mut self) {
        let metadata = VersionMetadata::new(
            ProtocolVersion::new(1, 2, 0),
            "2025-01-01T00:00:00Z",
        )
        .feature("L4 Privacy Hop with relay lottery")
        .feature("VRF-based delay mechanisms")
        .feature("Cover traffic generation")
        .feature("Enhanced Sphinx packet format")
        .feature("Backward compatibility with v1.1")
        .migration(
            "Current stable version. No migration needed.
New nodes should start directly with v1.2.0.",
        );

        self.versions.push(metadata);
    }

    /// Get metadata for a specific version
    pub fn get(&self, version: &ProtocolVersion) -> Option<&VersionMetadata> {
        self.versions.iter().find(|v| v.version == *version)
    }

    /// Get all versions
    pub fn all(&self) -> &[VersionMetadata] {
        &self.versions
    }

    /// Get latest version
    pub fn latest(&self) -> &VersionMetadata {
        self.versions
            .iter()
            .max_by(|a, b| a.version.cmp(&b.version))
            .expect("Registry must have at least one version")
    }

    /// Get all non-deprecated versions
    pub fn supported(&self) -> Vec<&VersionMetadata> {
        self.versions
            .iter()
            .filter(|v| !v.deprecated || !v.is_eol())
            .collect()
    }

    /// Check if a version is supported
    pub fn is_supported(&self, version: &ProtocolVersion) -> bool {
        self.get(version)
            .map(|v| !v.deprecated || !v.is_eol())
            .unwrap_or(false)
    }

    /// Get upgrade path from one version to another
    pub fn upgrade_path(
        &self,
        from: &ProtocolVersion,
        to: &ProtocolVersion,
    ) -> Option<Vec<&VersionMetadata>> {
        if from.major != to.major {
            // No upgrade path across major versions
            return None;
        }

        let mut path = Vec::new();
        for version in &self.versions {
            if version.version > *from && version.version <= *to {
                path.push(version);
            }
        }

        path.sort_by(|a, b| a.version.cmp(&b.version));
        Some(path)
    }
}

impl Default for VersionRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// Deprecation timeline
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeprecationTimeline {
    /// Version being deprecated
    pub version: ProtocolVersion,
    /// Deprecation announcement date
    pub announced: String,
    /// End of life date (no longer supported)
    pub eol: String,
    /// Recommended upgrade version
    pub upgrade_to: ProtocolVersion,
    /// Reason for deprecation
    pub reason: String,
}

impl DeprecationTimeline {
    /// Get v1.0.0 deprecation timeline
    pub fn v1_0_0() -> Self {
        Self {
            version: ProtocolVersion::new(1, 0, 0),
            announced: "2024-12-01T00:00:00Z".to_string(),
            eol: "2025-06-01T00:00:00Z".to_string(),
            upgrade_to: ProtocolVersion::V1_2_0,
            reason: "Lacks critical L4 privacy features and VRF-based security enhancements"
                .to_string(),
        }
    }

    /// Check if currently in deprecation window
    pub fn is_active(&self) -> bool {
        let now = Utc::now();

        if let (Ok(announced), Ok(eol)) = (
            DateTime::parse_from_rfc3339(&self.announced),
            DateTime::parse_from_rfc3339(&self.eol),
        ) {
            let announced_utc = announced.with_timezone(&Utc);
            let eol_utc = eol.with_timezone(&Utc);
            return now >= announced_utc && now < eol_utc;
        }

        false
    }

    /// Days until end of life
    pub fn days_until_eol(&self) -> Option<i64> {
        if let Ok(eol) = DateTime::parse_from_rfc3339(&self.eol) {
            let duration = eol.with_timezone(&Utc) - Utc::now();
            return Some(duration.num_days());
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version_registry() {
        let registry = VersionRegistry::new();

        // Should have all three versions
        assert_eq!(registry.all().len(), 3);

        // Latest should be v1.2.0
        assert_eq!(registry.latest().version, ProtocolVersion::V1_2_0);
    }

    #[test]
    fn test_version_lookup() {
        let registry = VersionRegistry::new();

        let v1_2 = registry.get(&ProtocolVersion::V1_2_0).unwrap();
        assert_eq!(v1_2.version, ProtocolVersion::V1_2_0);
        assert!(!v1_2.deprecated);
        assert!(!v1_2.features.is_empty());
    }

    #[test]
    fn test_upgrade_path() {
        let registry = VersionRegistry::new();

        let path = registry
            .upgrade_path(
                &ProtocolVersion::new(1, 0, 0),
                &ProtocolVersion::new(1, 2, 0),
            )
            .unwrap();

        // Should include v1.1.0 and v1.2.0
        assert_eq!(path.len(), 2);
        assert_eq!(path[0].version, ProtocolVersion::new(1, 1, 0));
        assert_eq!(path[1].version, ProtocolVersion::new(1, 2, 0));
    }

    #[test]
    fn test_supported_versions() {
        let registry = VersionRegistry::new();

        assert!(registry.is_supported(&ProtocolVersion::V1_2_0));
        assert!(registry.is_supported(&ProtocolVersion::V1_1_0));
    }

    #[test]
    fn test_deprecation_timeline() {
        let timeline = DeprecationTimeline::v1_0_0();

        assert_eq!(timeline.version, ProtocolVersion::new(1, 0, 0));
        assert_eq!(timeline.upgrade_to, ProtocolVersion::V1_2_0);
    }
}
