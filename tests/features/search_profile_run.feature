Feature: SearchProfile and SearchRun persistence
  As an operator
  I want SearchProfile criteria and SearchRun provenance stored in Core
  So that later HH vacancy acquisition can run against a stable contract

  Scenario: SearchRun freezes criteria and records item outcomes
    Given a SearchProfile with text "project manager"
    When I start a SearchRun with execution page_size 20
    And I change the SearchProfile text to "golang"
    Then the SearchRun criteria_snapshot text remains "project manager"
    And the SearchRun execution_snapshot contains page_size 20
    When I add a created SearchRunItem linked to a Vacancy
    And I add an error SearchRunItem without vacancy_id
    And I finalize the SearchRun as partial
    Then the SearchRun status is partial with finished_at set
    And counters match created 1 and error 1
