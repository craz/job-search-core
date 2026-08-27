Feature: ResumeVersion history semantics (R2.1.4)

  Scenario: Changed fixture content creates a new version while keeping the old
    Given an active HH resume link for resume A
    And a ResumeVersion v1 ingested from fixture content for resume A
    When the operator ingests changed fixture content for resume A
    Then a new ResumeVersion v2 is created
    And v1 remains readable by id
    And candidate-context current copy points at v2

  Scenario: Identical content after change does not create a third version
    Given ResumeVersions v1 and v2 for resume A where v2 is latest
    When the operator ingests content identical to v2
    Then no third ResumeVersion is created for resume A

  Scenario: Switch to unsynced resume then return and clear
    Given ResumeVersion history exists for resume A
    When the operator activates never-synced resume C
    Then candidate-context shows content_state not_synced for C
    When the operator activates resume A again
    Then candidate-context shows synced metadata for A's latest version
    When the operator clears the active HH resume
    Then candidate-context content_state is none
    And historical ResumeVersions for A remain readable
