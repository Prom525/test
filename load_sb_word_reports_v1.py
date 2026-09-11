CREATE TABLE IF NOT EXISTS sb_word_reports_parsed_v1 (
    id BIGSERIAL PRIMARY KEY,
    source_file TEXT UNIQUE,
    file_name TEXT,
    lijn_code TEXT,
    doc_date DATE,
    inspecteur TEXT,
    toezichthouder TEXT,
    uitvoeringstijd TEXT,
    werkvergunning TEXT,
    omschrijving TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sb_word_report_bands_v1 (
    id BIGSERIAL PRIMARY KEY,
    source_file TEXT,
    band_code TEXT,
    band_raw TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sb_word_report_checks_v1 (
    id BIGSERIAL PRIMARY KEY,
    source_file TEXT,
    band_code TEXT,
    omschrijving TEXT,
    ok_flag BOOLEAN,
    nok_flag BOOLEAN,
    opmerking TEXT,
    advies TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);