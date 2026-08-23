Operator System

Operator is an AI customer agent designed around a filesystem metaphor.

The interface should feel extremely close to a native macOS Finder window. Operator is not a dashboard, CRM, ticketing interface, or collection of SaaS panels. The product should behave like a customer relationship filesystem.

The core rule is simple:

Clients are folders. Everything that belongs to a client lives inside that client.

Root

The default Operator location is Clients.

The Clients view contains only client folders.

Examples:

Aster Bakery

Northwind Events

Kibo Foods

Mara Hotels

Atlas Dental

Lumina Studio

Do not mix calls, emails, PDFs, notes, requests, or other artifacts into the root Clients view.

The root should visually behave like Finder icon view: clean folders, generous spacing, minimal chrome, native-feeling navigation, and no dashboard widgets.

Client Folders

Opening a client folder reveals the customer relationship.

A client folder contains the information, communication, and business artifacts associated with that customer.

Typical subfolders may include:

Calls

Email

Documents

Requests

Notes

Depending on the connected business, additional folders may appear naturally, such as:

Orders

Appointments

Invoices

Deliveries

Projects

These should only exist when they make sense for that business.

The filesystem should not force every business into the same structure.

Files

Items inside client folders should behave like files.

Examples include:

call recordings

call transcripts

email threads

invoices

quotes

proposals

documents

requests

notes

order records

appointment records

The file metaphor should remain consistent.

A call can look and behave like an audio file.

An email thread can behave like a message file.

A PDF should remain a PDF.

A note should behave like a note or document.

Operator should avoid inventing abstract CRM objects when a familiar file-like representation works.

Sidebar

The sidebar follows Finder logic.

Items should represent locations, smart folders, groups, tags, integrations, or utilities.

A minimal structure can include:

Favorites

Recents

Shared

Clients

Needs You

Clients is the main customer directory.

Recents shows recently accessed or recently changed customer artifacts.

Shared contains items or client information shared with the user.

Needs You is a smart folder containing situations where Operator requires human judgment or approval.

Needs You must not become a dashboard. It is simply a filtered filesystem view.

Groups

Groups behave like folders or saved views.

Examples:

Prospects

Bakeries

Hotels

Studios

Groups should remain optional and should reflect how the business actually organizes customers.

Tags

Tags may be used in the same spirit as Finder tags.

Examples:

Waiting

Follow Up

Urgent

VIP

New

Tags should remain lightweight and optional.

They should not become hidden CRM stages or scores.

Utility

Trash

Trash remains available using familiar Finder behavior.

Operator should not add an Archive location by default.

Calls and Email

Calls and Email can exist in two ways.

First, each client can contain its own Calls and Email folders.

Second, Operator may expose global smart folders for Calls or Email if the user wants to browse those artifacts across every client.

For example:

Calls can show all call records across all clients.

Email can show all email threads across all clients.

If these global views exist, they are alternate filesystem views over the same underlying client data. They are not separate products or dashboards.

Navigation

Navigation should behave like Finder.

Users can:

open folders

move backward and forward

switch between icon, list, or column-style views

search

sort

group

tag

inspect items

move items to Trash

The visual language should remain native, quiet, and file-oriented.

Avoid unnecessary dividers, cards, pills, panels, dashboard sections, metrics, charts, customer scores, pipelines, and decorative UI.

If an element would feel strange inside Finder, it probably does not belong in Operator.

Plugins

Operator should include a Plugins button in the top-right toolbar.

Plugins connect Operator to external business systems and services.

Examples may include:

email providers

calendars

business databases

order systems

billing systems

support systems

delivery systems

internal tools

communication platforms

Plugins give Operator access to the systems it needs to understand and act on behalf of the business.

The Plugins interface should feel consistent with the Finder-inspired design rather than opening a dense app marketplace dashboard.

Skills

Operator should include a Skills button in the top-right toolbar.

Skills extend what Operator knows how to do.

A skill represents a reusable capability, instruction set, procedure, or domain-specific behavior that Operator can apply when working with customers.

Examples may include:

how the business handles custom orders

how refunds should be processed

how onboarding calls should be conducted

how appointment changes should be handled

how quotes should be prepared

how specific customer requests should be resolved

Skills should be addable and manageable without changing the core filesystem model.

Plugins give Operator access to systems.

Skills teach Operator how to work.

Customer Memory

Operator should maintain persistent memory for each customer.

The memory system should behave naturally rather than forcing the relationship into stages, health scores, pipelines, or artificial status fields.

Operator should remember relevant information such as:

who the customer is

previous conversations

preferences

requests

commitments

important facts

what has already been tried

what the business has told the customer

what the customer has told the business

When the customer returns, Operator continues from that context.

The customer folder is the visible home of that relationship.

Operator Behavior

Operator acts as the bridge between the customer and the business.

It can:

receive customer calls

make outbound calls

read and send email

retrieve business information

check connected systems

update connected systems

send documents

arrange appointments

coordinate orders

handle onboarding

follow up with customers

resolve routine requests

ask the business for help when judgment is required

Operator should act when it can and involve staff when it should not decide alone.

The human should not need to manage a workflow for every customer.

Operator simply continues handling the relationship.

Design Principle

Operator should feel like a filesystem for customer relationships.

The product should remain visually and conceptually close to Finder.

Do not redesign Finder into a SaaS dashboard.

Do not add product UI simply because typical business software has it.

The filesystem metaphor is the product structure.

Clients are folders. Customer interactions and business artifacts are files. Smart folders expose useful cross-client views. Plugins connect systems. Skills extend behavior. Operator handles the relationship.