# Change Log
All notable changes to mediaTUM will be documented in this file.

We mostly follow the conventions given in [Keep a Changelog](http://keepachangelog.com/) and relase a new version roughly once a month.
Calendar Versioning is used for our version numbers: http://calver.org/


## [v2017.03] - 2017-04-04

### Added

### Changed

### Fixed

- access to lower versions of a document returns an error
- wrong errormessage during upload of a file with a new version
- meta informations cannot be extracted from a pdf-document
- pdf metadata extraction problem
- too restrictive editor which denied upload of new files for some types


## [v2017.02] - 2017-03-16

### Added

- edit area with pagination to accelerate editor

### Changed

- upgraded to Nix packages 16.09
- removed obsolete edit modules: frontendparts, lza, ftp, license
- removed obsolete function for creating hashes in the identifier edit module
- removed obsolete ftp upload function
- removed obsolete upload webservice
- removed obsolete javascript zoom for image content type
- removed obsolete content types ImageStream and Project
- removed obsolete workflow steps ldapauth and checkdoublet
- removed obsolete meta field password
- removed obsolete metadata web service
- accelerate display of user statistics
- javascript zoom for images removed

### Fixed

- edit: moving files to subfolders in the edit area
- editmask with watermark metadata field cannot be saved
- editor linking child object detail to frontend
- various bugfixes


## [v2017.01] - 2017-02-14

### Changed

- removed obsolete integrated help
- check type of uploaded file when trying to exchange the digital object
- removed preview editor function for containers
- performance improvements

### Fixed

- problems when running mediaTUM without a config file
- Bibtex-Upload: accept non-standard records like @SCIENCEREPORT
- missing occurences list for search queries
- missing license icons
- Bibtex: www-address
- various bugfixes


## [v2016.12] - 2016-01-24

### Added

- Frontend: Users can change the number of displayed nodes in list views
- Example content for empty database: example schemas
- Citation type proceedings-article now allowed in DOI import

### Changed

- Better styling for headings: they don't look like links anymore
- Editor: start with user uploads dir instead of collections root

### Fixed

- Upload of files with umlauts or other non alphanumeric characters in the file name
- Display of version HTML
- Metafield name doublet creation
- Errors in mediatum configuration template
- More robust handling of bibtex file names


## [v2016.11] - 2016-12-16

### Changed

- Converted more TAL templates to Pug (ex-Jade) format
- Frame templates can now be customized in plugins by inheriting from builtin template pieces instead of replacing everything
- print view: deliver PDF with correct file ending

### Fixed

- BibTeX import
- Various frontend fixes, see git log
- Various editor fixes
- Various admin fixes
- mediatum.py --force-test-db 


## [v2016.10] - 2016-11-04

This is a large release with many incompatible changes. Only PostgreSQL is supported as main database and full text search DB from now on
Please contact us at mediatum@ub.tum.de before trying to migrate to this version!

### Changed

- Switched to PostgreSQL
- MySQL and SQLite are no longer supported
- Many more changes (will be documented later)

