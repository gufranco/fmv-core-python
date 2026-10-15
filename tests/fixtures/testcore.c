#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum {
    WIDTH = 4,
    HEIGHT = 2,
    PITCH_PIXELS = 8,
    ENV_GET_CAN_DUPE = 3,
    ENV_GET_SYSTEM_DIRECTORY = 9,
    ENV_UNKNOWN = 999,
    HAS_SYSTEM = 0x80,
    CAN_DUPE = 0x40,
    UNKNOWN_REFUSED = 0x20,
    NULL_REFUSED = 0x10,
    ENV_SET_PIXEL_FORMAT = 10,
    ENV_GET_VARIABLE = 15,
    ENV_SET_VARIABLES = 16,
    DEFAULT_READ = 0x04,
    MISSING_REFUSED = 0x02,
    OPTION_SET = 0x08,
    PIXEL_XRGB8888 = 1,
    DUPE_EVERY = 3
};

struct retro_game_info {
    const char *path;
    const void *data;
    size_t size;
    const char *meta;
};

struct retro_variable {
    const char *key;
    const char *value;
};

struct retro_system_info {
    const char *library_name;
    const char *library_version;
    const char *valid_extensions;
    bool need_fullpath;
    bool block_extract;
};

struct retro_game_geometry {
    unsigned base_width;
    unsigned base_height;
    unsigned max_width;
    unsigned max_height;
    float aspect_ratio;
};

struct retro_system_timing {
    double fps;
    double sample_rate;
};

struct retro_system_av_info {
    struct retro_game_geometry geometry;
    struct retro_system_timing timing;
};

typedef bool (*environment_t)(unsigned, void *);
typedef void (*video_t)(const void *, unsigned, unsigned, size_t);
typedef void (*audio_sample_t)(int16_t, int16_t);
typedef size_t (*audio_batch_t)(const int16_t *, size_t);
typedef void (*input_poll_t)(void);
typedef int16_t (*input_state_t)(unsigned, unsigned, unsigned, unsigned);

static environment_t environment;
static video_t video;
static audio_batch_t audio_batch;
static input_poll_t input_poll;
static uint32_t frame[PITCH_PIXELS * HEIGHT];
static uint32_t seed;
static unsigned count;
static uint32_t answers;

unsigned retro_api_version(void) { return 1; }
void retro_set_environment(environment_t callback) { environment = callback; }
void retro_set_video_refresh(video_t callback) { video = callback; }
void retro_set_audio_sample(audio_sample_t callback) { (void)callback; }
void retro_set_audio_sample_batch(audio_batch_t callback) { audio_batch = callback; }
void retro_set_input_poll(input_poll_t callback) { input_poll = callback; }
void retro_set_input_state(input_state_t callback) { (void)callback; }

void retro_init(void) { count = 0; }
void retro_deinit(void) {}

void retro_get_system_info(struct retro_system_info *info) {
    memset(info, 0, sizeof(*info));
    info->library_name = "testcore";
    info->library_version = "1";
    info->valid_extensions = "bin";
}

void retro_get_system_av_info(struct retro_system_av_info *info) {
    memset(info, 0, sizeof(*info));
    info->geometry.base_width = WIDTH;
    info->geometry.base_height = HEIGHT;
    info->geometry.max_width = WIDTH;
    info->geometry.max_height = HEIGHT;
    info->timing.fps = 60.0;
    info->timing.sample_rate = 48000.0;
}

bool retro_load_game(const struct retro_game_info *game) {
    const char *system = NULL;
    unsigned format = PIXEL_XRGB8888;
    bool dupe = false;
    unsigned unknown = 0;
    struct retro_variable option = {"test_option", NULL};
    struct retro_variable fallback = {"test_default", NULL};
    struct retro_variable missing = {"test_missing", NULL};
    struct retro_variable declared[] = {
        {"test_option", "Test option; off|on"},
        {"test_default", "Test default; one|two"},
        {NULL, NULL},
    };
    if (game == NULL || game->data == NULL || game->size == 0) {
        return false;
    }
    seed = ((const uint8_t *)game->data)[0];
    answers = 0;
    environment(ENV_SET_VARIABLES, declared);
    if (environment(ENV_GET_SYSTEM_DIRECTORY, (void *)&system) && system != NULL) {
        answers |= HAS_SYSTEM;
    }
    if (environment(ENV_GET_CAN_DUPE, &dupe) && dupe) {
        answers |= CAN_DUPE;
    }
    if (!environment(ENV_UNKNOWN, &unknown)) {
        answers |= UNKNOWN_REFUSED;
    }
    if (!environment(ENV_GET_SYSTEM_DIRECTORY, NULL)) {
        answers |= NULL_REFUSED;
    }
    if (environment(ENV_GET_VARIABLE, &option) && option.value != NULL && strcmp(option.value, "on") == 0) {
        answers |= OPTION_SET;
    }
    if (environment(ENV_GET_VARIABLE, &fallback) && fallback.value != NULL && strcmp(fallback.value, "one") == 0) {
        answers |= DEFAULT_READ;
    }
    if (!environment(ENV_GET_VARIABLE, &missing)) {
        answers |= MISSING_REFUSED;
    }
    return environment(ENV_SET_PIXEL_FORMAT, &format);
}

void retro_unload_game(void) {}

void retro_run(void) {
    int16_t silence[4] = {0, 0, 0, 0};
    input_poll();
    audio_batch(silence, 2);
    if (count % DUPE_EVERY == DUPE_EVERY - 1) {
        video(NULL, WIDTH, HEIGHT, PITCH_PIXELS * sizeof(uint32_t));
        count += 1;
        return;
    }
    for (unsigned y = 0; y < HEIGHT; y += 1) {
        for (unsigned x = 0; x < WIDTH; x += 1) {
            uint32_t red = (seed + count) & 0xFF;
            uint32_t green = (x * 16 + y) & 0xFF;
            uint32_t blue = answers;
            frame[y * PITCH_PIXELS + x] = (red << 16) | (green << 8) | blue;
        }
    }
    video(frame, WIDTH, HEIGHT, PITCH_PIXELS * sizeof(uint32_t));
    count += 1;
}
