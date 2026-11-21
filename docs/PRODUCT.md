# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Primary: data providers of AED information in Poland – municipalities, schools, hospitals, companies, fire brigades (OSP) – usually a clerk with an existing spreadsheet, logged into the dane.gov.pl provider panel. Their job: publish the institution's AED list once, correctly, and keep it current with minimal effort.
Secondary: the dane.gov.pl operator (Departament Zarządzania Danymi, Ministerstwo Cyfryzacji) and data consumers such as 112 dispatch and apps, who need one national, machine-readable dataset with availability by time of day. Citizens are a tertiary audience.

## Product Purpose
„Naładuj mapę Polski.” is an AED module inside the dane.gov.pl portal (fork of its open source code): a 5-step wizard that turns any institution file (CSV/XLSX) into a native dataset following a model data scope, automatic correction and blocking of errors, an automatically aggregated national dataset with API, and a campaign that motivates providers. Success: many institutions publish, the national dataset becomes complete and current.

## Positioning
Lives inside dane.gov.pl rather than as a separate service: provider accounts, native datasets, the portal's quality rules, licences and comment mechanism. Each institution owns its dataset; the portal aggregates.

## Constraints
- Must stay within the portal frame (header, footer, navigation) and work with the portal's high-contrast modes (body.black-white, body.black-yellow, body.yellow-black) and font-size controls.
- WCAG (current version), responsive, Polish and English.
- Brand commitments: name and slogan „Naładuj mapę Polski.”, instruction „Udostępnij dane o swoim AED w dane.gov.pl.”, colours navy #0B2545, red #D62839, cream #F7F4EE, no green (avoids confusion with the ISO 7010 AED sign), logo = angular Poland outline with a red pulse.
- No invented statistics; figures come from the live API.

## Voice
Invitation and agency. No fear, no shaming. Short, concrete Polish.
