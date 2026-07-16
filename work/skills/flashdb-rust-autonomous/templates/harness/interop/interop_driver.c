#include <flashdb.h>

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define KV_SEC_SIZE 4096U
#define KV_MAX_SIZE (KV_SEC_SIZE * 4U)
#define TS_SEC_SIZE 4096U
#define TS_MAX_SIZE (TS_SEC_SIZE * 16U)

static unsigned int lock_count;
static unsigned int unlock_count;
static fdb_time_t clock_value = 300;

static void fail(const char *message)
{
    fprintf(stderr, "INTEROP_DRIVER_FAIL: %s\n", message);
    exit(1);
}

static void require_true(bool condition, const char *message)
{
    if (!condition) {
        fail(message);
    }
}

static void lock_db(fdb_db_t db)
{
    (void)db;
    lock_count++;
}

static void unlock_db(fdb_db_t db)
{
    (void)db;
    unlock_count++;
}

static void verify_lock_contract(void)
{
    require_true(lock_count > 0, "lock callback was not invoked");
    require_true(lock_count == unlock_count, "lock/unlock callback counts differ");
}

static fdb_time_t get_time(void)
{
    return ++clock_value;
}

static void ensure_directory(const char *path)
{
    if (mkdir(path, 0777) != 0 && errno != EEXIST) {
        fail("cannot create database directory");
    }
}

static void configure_kvdb(struct fdb_kvdb *db)
{
    uint32_t sec_size = KV_SEC_SIZE;
    uint32_t max_size = KV_MAX_SIZE;
    uint32_t observed_sec_size = 0;
    bool file_mode = true;
    bool not_formatable = false;

    memset(db, 0, sizeof(*db));
    fdb_kvdb_control(db, FDB_KVDB_CTRL_SET_SEC_SIZE, &sec_size);
    fdb_kvdb_control(db, FDB_KVDB_CTRL_GET_SEC_SIZE, &observed_sec_size);
    require_true(observed_sec_size == sec_size, "KVDB sector-size control mismatch");
    fdb_kvdb_control(db, FDB_KVDB_CTRL_SET_LOCK, (void *)lock_db);
    fdb_kvdb_control(db, FDB_KVDB_CTRL_SET_UNLOCK, (void *)unlock_db);
    fdb_kvdb_control(db, FDB_KVDB_CTRL_SET_FILE_MODE, &file_mode);
    fdb_kvdb_control(db, FDB_KVDB_CTRL_SET_MAX_SIZE, &max_size);
    fdb_kvdb_control(db, FDB_KVDB_CTRL_SET_NOT_FORMAT, &not_formatable);
}

static void kv_check_uninitialized(void)
{
    struct fdb_kvdb db;

    memset(&db, 0, sizeof(db));
    require_true(fdb_calc_crc32(0, "123456789", 9) == 0xcbf43926U,
                 "CRC32 oracle mismatch");
    require_true(fdb_kvdb_check(&db) == FDB_INIT_FAILED,
                 "fdb_kvdb_check must reject an uninitialized database");
}

static void kv_produce(const char *path)
{
    static const uint8_t binary_value[] = {0x00, 0x01, 0x02, 0x7f, 0x80, 0xff};
    struct fdb_kvdb db;
    struct fdb_blob blob;

    lock_count = 0;
    unlock_count = 0;
    ensure_directory(path);
    configure_kvdb(&db);
    require_true(fdb_kvdb_init(&db, "interop_kv", path, NULL, NULL) == FDB_NO_ERR,
                 "KVDB init failed");
    require_true(fdb_kv_set(&db, "greeting", "interop-value") == FDB_NO_ERR,
                 "KV string write failed");
    require_true(fdb_kv_set_blob(&db, "binary",
                                 fdb_blob_make(&blob, binary_value, sizeof(binary_value))) == FDB_NO_ERR,
                 "KV blob write failed");
    require_true(fdb_kvdb_check(&db) == FDB_NO_ERR, "KVDB integrity check failed");
    fdb_kv_print(&db);
    require_true(fdb_kvdb_deinit(&db) == FDB_NO_ERR, "KVDB deinit failed");
    verify_lock_contract();
}

static void kv_verify(const char *path)
{
    static const uint8_t expected_binary[] = {0x00, 0x01, 0x02, 0x7f, 0x80, 0xff};
    uint8_t actual_binary[sizeof(expected_binary)] = {0};
    struct fdb_kv_iterator iterator;
    struct fdb_kvdb db;
    struct fdb_blob blob;
    const char *value;
    size_t length;
    size_t count = 0;

    lock_count = 0;
    unlock_count = 0;
    configure_kvdb(&db);
    require_true(fdb_kvdb_init(&db, "interop_kv", path, NULL, NULL) == FDB_NO_ERR,
                 "KVDB reopen failed");
    value = fdb_kv_get(&db, "greeting");
    require_true(value != NULL && strcmp(value, "interop-value") == 0,
                 "KV string read mismatch");
    length = fdb_kv_get_blob(&db, "binary",
                             fdb_blob_make(&blob, actual_binary, sizeof(actual_binary)));
    require_true(length == sizeof(expected_binary), "KV blob length mismatch");
    require_true(memcmp(actual_binary, expected_binary, sizeof(expected_binary)) == 0,
                 "KV blob content mismatch");
    require_true(fdb_kv_get_obj(&db, "binary", &iterator.curr_kv) != NULL,
                 "KV object lookup failed");
    fdb_kv_iterator_init(&db, &iterator);
    while (fdb_kv_iterate(&db, &iterator)) {
        count++;
    }
    require_true(count == 2, "KV iterator count mismatch");
    require_true(fdb_kvdb_check(&db) == FDB_NO_ERR, "KVDB integrity check after reopen failed");
    fdb_kv_print(&db);
    require_true(fdb_kvdb_deinit(&db) == FDB_NO_ERR, "KVDB reopen deinit failed");
    verify_lock_contract();
}

struct ts_verify_context {
    struct fdb_tsdb *db;
    size_t count;
};

static bool verify_tsl(fdb_tsl_t tsl, void *arg)
{
    static const uint8_t first[] = {'a', 'l', 'p', 'h', 'a'};
    static const uint8_t second[] = {0x10, 0x20, 0x00, 0x40};
    struct ts_verify_context *context = arg;
    struct fdb_blob blob;
    uint8_t data[8] = {0};
    size_t length;

    require_true(tsl->status == FDB_TSL_WRITE, "TSL status mismatch");
    require_true(tsl->log_len <= sizeof(data), "TSL length exceeds test buffer");
    length = fdb_blob_read((fdb_db_t)context->db,
                           fdb_tsl_to_blob(tsl, fdb_blob_make(&blob, data, sizeof(data))));
    if (context->count == 0) {
        require_true(tsl->time == 100, "first TSL timestamp mismatch");
        require_true(length == sizeof(first) && memcmp(data, first, sizeof(first)) == 0,
                     "first TSL data mismatch");
    } else if (context->count == 1) {
        require_true(tsl->time == 200, "second TSL timestamp mismatch");
        require_true(length == sizeof(second) && memcmp(data, second, sizeof(second)) == 0,
                     "second TSL data mismatch");
    } else {
        fail("unexpected extra TSL");
    }
    context->count++;
    return false;
}

static bool count_tsl(fdb_tsl_t tsl, void *arg)
{
    size_t *count = arg;

    require_true(tsl->status == FDB_TSL_WRITE, "reverse iterator status mismatch");
    (*count)++;
    return false;
}

static void configure_tsdb(struct fdb_tsdb *db)
{
    uint32_t sec_size = TS_SEC_SIZE;
    uint32_t max_size = TS_MAX_SIZE;
    uint32_t observed_sec_size = 0;
    bool file_mode = true;
    bool not_formatable = false;

    memset(db, 0, sizeof(*db));
    fdb_tsdb_control(db, FDB_TSDB_CTRL_SET_SEC_SIZE, &sec_size);
    fdb_tsdb_control(db, FDB_TSDB_CTRL_GET_SEC_SIZE, &observed_sec_size);
    require_true(observed_sec_size == sec_size, "TSDB sector-size control mismatch");
    fdb_tsdb_control(db, FDB_TSDB_CTRL_SET_LOCK, (void *)lock_db);
    fdb_tsdb_control(db, FDB_TSDB_CTRL_SET_UNLOCK, (void *)unlock_db);
    fdb_tsdb_control(db, FDB_TSDB_CTRL_SET_FILE_MODE, &file_mode);
    fdb_tsdb_control(db, FDB_TSDB_CTRL_SET_MAX_SIZE, &max_size);
    fdb_tsdb_control(db, FDB_TSDB_CTRL_SET_NOT_FORMAT, &not_formatable);
}

static void ts_produce(const char *path)
{
    static const uint8_t first[] = {'a', 'l', 'p', 'h', 'a'};
    static const uint8_t second[] = {0x10, 0x20, 0x00, 0x40};
    struct fdb_tsdb db;
    struct fdb_blob blob;
    bool rollover = false;
    bool observed_rollover = true;
    fdb_time_t last_time = 0;

    lock_count = 0;
    unlock_count = 0;
    ensure_directory(path);
    configure_tsdb(&db);
    require_true(fdb_tsdb_init(&db, "interop_ts", path, get_time, 32, NULL) == FDB_NO_ERR,
                 "TSDB init failed");
    fdb_tsdb_control(&db, FDB_TSDB_CTRL_SET_ROLLOVER, &rollover);
    fdb_tsdb_control(&db, FDB_TSDB_CTRL_GET_ROLLOVER, &observed_rollover);
    require_true(!observed_rollover, "TSDB rollover control mismatch");
    require_true(fdb_tsl_append_with_ts(&db, fdb_blob_make(&blob, first, sizeof(first)), 100) == FDB_NO_ERR,
                 "first TSL append failed");
    require_true(fdb_tsl_append_with_ts(&db, fdb_blob_make(&blob, second, sizeof(second)), 200) == FDB_NO_ERR,
                 "second TSL append failed");
    fdb_tsdb_control(&db, FDB_TSDB_CTRL_GET_LAST_TIME, &last_time);
    require_true(last_time == 200, "TSDB last-time control mismatch");
    require_true(fdb_tsl_query_count(&db, 0, 300, FDB_TSL_WRITE) == 2,
                 "TSDB query count after append mismatch");
    require_true(fdb_tsl_max_blob_count(&db) > 0, "TSDB maximum blob count must be nonzero");
    require_true(fdb_tsdb_deinit(&db) == FDB_NO_ERR, "TSDB deinit failed");
    verify_lock_contract();
}

static void ts_verify(const char *path)
{
    struct fdb_tsdb db;
    struct ts_verify_context context = {0};
    size_t reverse_count = 0;

    lock_count = 0;
    unlock_count = 0;
    configure_tsdb(&db);
    require_true(fdb_tsdb_init(&db, "interop_ts", path, get_time, 32, NULL) == FDB_NO_ERR,
                 "TSDB reopen failed");
    context.db = &db;
    fdb_tsl_iter(&db, verify_tsl, &context);
    require_true(context.count == 2, "TSDB iterator count mismatch");
    fdb_tsl_iter_reverse(&db, count_tsl, &reverse_count);
    require_true(reverse_count == 2, "TSDB reverse iterator count mismatch");
    require_true(fdb_tsl_query_count(&db, 0, 300, FDB_TSL_WRITE) == 2,
                 "TSDB query count after reopen mismatch");
    require_true(fdb_tsdb_deinit(&db) == FDB_NO_ERR, "TSDB reopen deinit failed");
    verify_lock_contract();
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "kv-check-uninitialized") == 0) {
        kv_check_uninitialized();
    } else if (argc == 3 && strcmp(argv[1], "kv-produce") == 0) {
        kv_produce(argv[2]);
    } else if (argc == 3 && strcmp(argv[1], "kv-verify") == 0) {
        kv_verify(argv[2]);
    } else if (argc == 3 && strcmp(argv[1], "ts-produce") == 0) {
        ts_produce(argv[2]);
    } else if (argc == 3 && strcmp(argv[1], "ts-verify") == 0) {
        ts_verify(argv[2]);
    } else {
        fprintf(stderr, "usage: %s MODE [DIRECTORY]\n", argv[0]);
        return 2;
    }
    puts("INTEROP_DRIVER_PASS");
    return 0;
}
