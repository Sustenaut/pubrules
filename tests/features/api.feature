Feature: pubrules.api is the one surface sibling packages import
  pubfleet and pubhost use pubrules as a library, through pubrules.api only.
  Each name there lives in its own module, so an internal can move freely,
  but the surface itself is held to tests/fixtures/api.txt: every name, with
  its signature, its pattern or its value. Any change to the surface fails
  here first, until the fixture is updated on purpose and the change
  recorded with pubrel add (removed or changed for a name dropped or
  reshaped, added for a new one).

  Scenario: The surface is the one the fixture records
    When I read the shape of every name pubrules.api exports
    Then it is the shape tests/fixtures/api.txt records

  Scenario: Every exported name can be imported
    When I read the shape of every name pubrules.api exports
    Then each name is importable from pubrules.api

  Scenario: Nothing inside pubrules imports its own surface
    When I read every import in src/pubrules
    Then none is of pubrules.api
