Feature: Sharing a chat via a deep link
  Scenario: The share control is present in the chat   # BEH-1
    Given I am in a chat
    Then a share control is available in the chat toolbar

  Scenario: Sharing copies a link to this chat   # BEH-4, BEH-5
    Given I am in a chat
    When I share the chat
    Then a link to this chat is copied to my clipboard
    And the link identifies this conversation

  Scenario: Sharing confirms the link was copied   # BEH-7
    Given I am in a chat
    When I share the chat
    Then the control confirms the link was copied
