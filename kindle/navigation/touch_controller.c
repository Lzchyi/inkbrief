#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <time.h>
#include <unistd.h>

#define MAX_EVENT_DEVICES 32
#define BITS_PER_LONG (sizeof(unsigned long) * 8U)
#define BIT_WORD(bit) ((bit) / BITS_PER_LONG)
#define BIT_MASK(bit) (1UL << ((bit) % BITS_PER_LONG))
#define NBITS(max) (((max) + BITS_PER_LONG) / BITS_PER_LONG)

struct options {
    const char *device;
    int width;
    int height;
    int timeout_seconds;
    int home_width;
    int home_height;
    int hold_ms;
    bool swap_axes;
    bool invert_x;
    bool invert_y;
    bool probe_only;
};

struct axis_range {
    int minimum;
    int maximum;
};

struct touch_state {
    bool active;
    bool have_x;
    bool have_y;
    int raw_x;
    int raw_y;
    int start_x;
    int start_y;
    int current_x;
    int current_y;
    int64_t started_ms;
    int64_t corner_started_ms;
};

static volatile sig_atomic_t stop_requested = 0;
static int input_fd = -1;
static bool input_grabbed = false;

static void handle_signal(int signal_number)
{
    (void)signal_number;
    stop_requested = 1;
}

static void release_input(void)
{
    if (input_fd >= 0) {
        if (input_grabbed) {
            (void)ioctl(input_fd, EVIOCGRAB, 0);
            input_grabbed = false;
        }
        (void)close(input_fd);
        input_fd = -1;
    }
}

static int64_t monotonic_ms(void)
{
    struct timespec now;

    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        return -1;
    }
    return ((int64_t)now.tv_sec * 1000) + (now.tv_nsec / 1000000);
}

static bool bit_is_set(const unsigned long *bits, unsigned int bit)
{
    return (bits[BIT_WORD(bit)] & BIT_MASK(bit)) != 0;
}

static bool parse_positive_int(const char *value, int *output)
{
    char *end = NULL;
    long parsed;

    errno = 0;
    parsed = strtol(value, &end, 10);
    if (errno != 0 || end == value || *end != '\0' || parsed <= 0 || parsed > 86400000L) {
        return false;
    }
    *output = (int)parsed;
    return true;
}

static void usage(FILE *stream)
{
    fprintf(stream,
            "usage: touch-controller [--device PATH] --width PX --height PX "
            "--timeout SEC --home-width PX --home-height PX --hold-ms MS "
            "[--swap-axes] [--invert-x] [--invert-y] [--probe]\n");
}

static bool parse_options(int argc, char **argv, struct options *options)
{
    int index;

    memset(options, 0, sizeof(*options));
    options->width = 1072;
    options->height = 1448;
    options->timeout_seconds = 1800;
    options->home_width = 180;
    options->home_height = 110;
    options->hold_ms = 3000;

    for (index = 1; index < argc; ++index) {
        const char *argument = argv[index];

        if (strcmp(argument, "--swap-axes") == 0) {
            options->swap_axes = true;
        } else if (strcmp(argument, "--invert-x") == 0) {
            options->invert_x = true;
        } else if (strcmp(argument, "--invert-y") == 0) {
            options->invert_y = true;
        } else if (strcmp(argument, "--probe") == 0) {
            options->probe_only = true;
        } else if (strcmp(argument, "--help") == 0) {
            usage(stdout);
            exit(EXIT_SUCCESS);
        } else if (index + 1 >= argc) {
            return false;
        } else if (strcmp(argument, "--device") == 0) {
            options->device = argv[++index];
        } else if (strcmp(argument, "--width") == 0) {
            if (!parse_positive_int(argv[++index], &options->width)) {
                return false;
            }
        } else if (strcmp(argument, "--height") == 0) {
            if (!parse_positive_int(argv[++index], &options->height)) {
                return false;
            }
        } else if (strcmp(argument, "--timeout") == 0) {
            if (!parse_positive_int(argv[++index], &options->timeout_seconds)) {
                return false;
            }
        } else if (strcmp(argument, "--home-width") == 0) {
            if (!parse_positive_int(argv[++index], &options->home_width)) {
                return false;
            }
        } else if (strcmp(argument, "--home-height") == 0) {
            if (!parse_positive_int(argv[++index], &options->home_height)) {
                return false;
            }
        } else if (strcmp(argument, "--hold-ms") == 0) {
            if (!parse_positive_int(argv[++index], &options->hold_ms)) {
                return false;
            }
        } else {
            return false;
        }
    }

    return options->timeout_seconds <= 28800 && options->hold_ms >= 3000 &&
           options->home_width < options->width && options->home_height < options->height;
}

static int device_score(int fd, char *name, size_t name_size, bool *uses_multitouch)
{
    unsigned long event_bits[NBITS(EV_MAX + 1)] = {0};
    unsigned long absolute_bits[NBITS(ABS_MAX + 1)] = {0};
    int score = 0;

    memset(name, 0, name_size);
    (void)ioctl(fd, EVIOCGNAME(name_size), name);
    if (ioctl(fd, EVIOCGBIT(0, sizeof(event_bits)), event_bits) < 0 ||
        !bit_is_set(event_bits, EV_ABS)) {
        return -1;
    }
    if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(absolute_bits)), absolute_bits) < 0) {
        return -1;
    }

    *uses_multitouch = bit_is_set(absolute_bits, ABS_MT_POSITION_X) &&
                       bit_is_set(absolute_bits, ABS_MT_POSITION_Y);
    if (*uses_multitouch) {
        score += 20;
    } else if (bit_is_set(absolute_bits, ABS_X) && bit_is_set(absolute_bits, ABS_Y)) {
        score += 10;
    } else {
        return -1;
    }

    if (strstr(name, "touch") != NULL || strstr(name, "Touch") != NULL) {
        score += 5;
    }
    return score;
}

static int open_touch_device(const char *requested_path, char *chosen_path, size_t path_size,
                             char *chosen_name, size_t name_size, bool *uses_multitouch)
{
    int best_fd = -1;
    int best_score = -1;
    int first = 0;
    int last = MAX_EVENT_DEVICES;
    int index;

    if (requested_path != NULL) {
        first = -1;
        last = 0;
    }

    for (index = first; index < last; ++index) {
        char path[64];
        char name[256];
        bool candidate_multitouch = false;
        int candidate_fd;
        int score;

        if (requested_path != NULL) {
            if (snprintf(path, sizeof(path), "%s", requested_path) >= (int)sizeof(path)) {
                return -1;
            }
        } else {
            (void)snprintf(path, sizeof(path), "/dev/input/event%d", index);
        }

        candidate_fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (candidate_fd < 0) {
            continue;
        }
        score = device_score(candidate_fd, name, sizeof(name), &candidate_multitouch);
        if (score > best_score) {
            if (best_fd >= 0) {
                (void)close(best_fd);
            }
            best_fd = candidate_fd;
            best_score = score;
            *uses_multitouch = candidate_multitouch;
            (void)snprintf(chosen_path, path_size, "%s", path);
            (void)snprintf(chosen_name, name_size, "%s", name);
        } else {
            (void)close(candidate_fd);
        }
        if (requested_path != NULL) {
            break;
        }
    }
    return best_fd;
}

static bool get_axis_range(int fd, unsigned int code, struct axis_range *range)
{
    struct input_absinfo info;

    memset(&info, 0, sizeof(info));
    if (ioctl(fd, EVIOCGABS(code), &info) < 0 || info.maximum <= info.minimum) {
        return false;
    }
    range->minimum = info.minimum;
    range->maximum = info.maximum;
    return true;
}

static int scale_axis(int raw, const struct axis_range *range, int logical_size)
{
    int64_t numerator;
    int value;

    if (raw < range->minimum) {
        raw = range->minimum;
    } else if (raw > range->maximum) {
        raw = range->maximum;
    }
    numerator = (int64_t)(raw - range->minimum) * (logical_size - 1);
    value = (int)(numerator / (range->maximum - range->minimum));
    return value;
}

static void transform_coordinates(const struct options *options,
                                  const struct axis_range *x_range,
                                  const struct axis_range *y_range,
                                  int raw_x, int raw_y, int *x, int *y)
{
    int logical_x;
    int logical_y;

    if (options->swap_axes) {
        logical_x = scale_axis(raw_y, y_range, options->width);
        logical_y = scale_axis(raw_x, x_range, options->height);
    } else {
        logical_x = scale_axis(raw_x, x_range, options->width);
        logical_y = scale_axis(raw_y, y_range, options->height);
    }
    if (options->invert_x) {
        logical_x = options->width - 1 - logical_x;
    }
    if (options->invert_y) {
        logical_y = options->height - 1 - logical_y;
    }
    *x = logical_x;
    *y = logical_y;
}

static void emit_event(const char *event)
{
    (void)puts(event);
    (void)fflush(stdout);
}

static void begin_touch(struct touch_state *touch, int64_t now)
{
    memset(touch, 0, sizeof(*touch));
    touch->active = true;
    touch->started_ms = now;
    touch->corner_started_ms = -1;
}

static bool point_in_home(const struct options *options, int x, int y)
{
    return x >= 0 && x < options->home_width && y >= 0 && y < options->home_height;
}

static bool point_in_failsafe_corner(const struct options *options, int x, int y)
{
    return x >= options->width - options->home_width && x < options->width &&
           y >= 0 && y < options->home_height;
}

static bool finish_touch(const struct options *options, struct touch_state *touch, int64_t now)
{
    int delta_x;
    int delta_y;
    int absolute_x;
    int absolute_y;
    int threshold = options->width / 5;
    int64_t duration;

    if (!touch->active) {
        return false;
    }
    touch->active = false;
    if (!touch->have_x || !touch->have_y) {
        return false;
    }

    delta_x = touch->current_x - touch->start_x;
    delta_y = touch->current_y - touch->start_y;
    absolute_x = delta_x < 0 ? -delta_x : delta_x;
    absolute_y = delta_y < 0 ? -delta_y : delta_y;
    duration = now - touch->started_ms;
    if (threshold < 120) {
        threshold = 120;
    }

    if (point_in_home(options, touch->start_x, touch->start_y) &&
        point_in_home(options, touch->current_x, touch->current_y) &&
        absolute_x < 60 && absolute_y < 60) {
        emit_event("HOME");
        return true;
    }
    if (duration <= 3000 && absolute_x >= threshold && absolute_x > absolute_y * 2) {
        emit_event(delta_x < 0 ? "NEXT" : "PREVIOUS");
    }
    return false;
}

static bool update_touch_position(const struct options *options,
                                  const struct axis_range *x_range,
                                  const struct axis_range *y_range,
                                  struct touch_state *touch, int64_t now)
{
    int x;
    int y;

    if (!touch->active || !touch->have_x || !touch->have_y) {
        return false;
    }
    transform_coordinates(options, x_range, y_range, touch->raw_x, touch->raw_y, &x, &y);
    touch->current_x = x;
    touch->current_y = y;
    if (touch->start_x == -1 && touch->start_y == -1) {
        touch->start_x = x;
        touch->start_y = y;
    }

    if (point_in_failsafe_corner(options, x, y)) {
        if (touch->corner_started_ms < 0) {
            touch->corner_started_ms = now;
        } else if (now - touch->corner_started_ms >= options->hold_ms) {
            emit_event("HOME");
            return true;
        }
    } else {
        touch->corner_started_ms = -1;
    }
    return false;
}

int main(int argc, char **argv)
{
    struct options options;
    struct axis_range x_range;
    struct axis_range y_range;
    struct touch_state touch;
    struct sigaction action;
    char device_path[64];
    char device_name[256];
    bool uses_multitouch = false;
    unsigned int x_code;
    unsigned int y_code;
    int64_t deadline;

    if (!parse_options(argc, argv, &options)) {
        usage(stderr);
        return EXIT_FAILURE;
    }

    input_fd = open_touch_device(options.device, device_path, sizeof(device_path),
                                 device_name, sizeof(device_name), &uses_multitouch);
    if (input_fd < 0) {
        emit_event("ERROR:no-touch-input");
        return 2;
    }
    if (atexit(release_input) != 0) {
        release_input();
        return 2;
    }

    x_code = uses_multitouch ? ABS_MT_POSITION_X : ABS_X;
    y_code = uses_multitouch ? ABS_MT_POSITION_Y : ABS_Y;
    if (!get_axis_range(input_fd, x_code, &x_range) ||
        !get_axis_range(input_fd, y_code, &y_range)) {
        emit_event("ERROR:invalid-touch-range");
        return 2;
    }

    if (options.probe_only) {
        printf("input_device=%s\ninput_name=%s\ninput_protocol=%s\n"
               "raw_min_x=%d\nraw_max_x=%d\nraw_min_y=%d\nraw_max_y=%d\n",
               device_path, device_name, uses_multitouch ? "multitouch" : "single-touch",
               x_range.minimum, x_range.maximum, y_range.minimum, y_range.maximum);
        return EXIT_SUCCESS;
    }

    memset(&action, 0, sizeof(action));
    action.sa_handler = handle_signal;
    sigemptyset(&action.sa_mask);
    (void)sigaction(SIGINT, &action, NULL);
    (void)sigaction(SIGTERM, &action, NULL);
    (void)sigaction(SIGHUP, &action, NULL);
    (void)sigaction(SIGQUIT, &action, NULL);

    #ifdef PR_SET_PDEATHSIG
    if (prctl(PR_SET_PDEATHSIG, SIGTERM) != 0 || getppid() == 1) {
        emit_event("ERROR:parent-watch-failed");
        return 3;
    }
    #endif

    if (ioctl(input_fd, EVIOCGRAB, 1) < 0) {
        emit_event("ERROR:input-grab-failed");
        return 3;
    }
    input_grabbed = true;

    memset(&touch, 0, sizeof(touch));
    touch.start_x = -1;
    touch.start_y = -1;
    deadline = monotonic_ms() + ((int64_t)options.timeout_seconds * 1000);

    while (!stop_requested) {
        struct pollfd descriptor;
        int64_t now = monotonic_ms();
        int poll_timeout;
        int poll_result;

        if (now < 0 || now >= deadline) {
            emit_event("TIMEOUT");
            break;
        }
        if (update_touch_position(&options, &x_range, &y_range, &touch, now)) {
            break;
        }

        poll_timeout = (int)(deadline - now);
        if (touch.active && touch.corner_started_ms >= 0 && poll_timeout > 100) {
            poll_timeout = 100;
        }
        descriptor.fd = input_fd;
        descriptor.events = POLLIN;
        descriptor.revents = 0;
        poll_result = poll(&descriptor, 1, poll_timeout);
        if (poll_result < 0) {
            if (errno == EINTR) {
                continue;
            }
            emit_event("ERROR:input-poll-failed");
            break;
        }
        if (poll_result == 0) {
            continue;
        }
        if ((descriptor.revents & (POLLERR | POLLHUP | POLLNVAL)) != 0) {
            emit_event("ERROR:input-device-lost");
            break;
        }
        if ((descriptor.revents & POLLIN) != 0) {
            struct input_event events[32];
            ssize_t bytes_read = read(input_fd, events, sizeof(events));
            size_t event_count;
            size_t index;

            if (bytes_read < 0) {
                if (errno == EAGAIN || errno == EINTR) {
                    continue;
                }
                emit_event("ERROR:input-read-failed");
                break;
            }
            if ((size_t)bytes_read % sizeof(struct input_event) != 0) {
                emit_event("ERROR:partial-input-event");
                break;
            }
            event_count = (size_t)bytes_read / sizeof(struct input_event);
            for (index = 0; index < event_count; ++index) {
                const struct input_event *event = &events[index];
                now = monotonic_ms();

                if (event->type == EV_ABS && event->code == x_code) {
                    touch.raw_x = event->value;
                    touch.have_x = true;
                } else if (event->type == EV_ABS && event->code == y_code) {
                    touch.raw_y = event->value;
                    touch.have_y = true;
                } else if (uses_multitouch && event->type == EV_ABS &&
                           event->code == ABS_MT_TRACKING_ID) {
                    if (event->value >= 0) {
                        begin_touch(&touch, now);
                        touch.start_x = -1;
                        touch.start_y = -1;
                    } else if (finish_touch(&options, &touch, now)) {
                        stop_requested = 1;
                        break;
                    }
                } else if (!uses_multitouch && event->type == EV_KEY &&
                           event->code == BTN_TOUCH) {
                    if (event->value != 0) {
                        begin_touch(&touch, now);
                        touch.start_x = -1;
                        touch.start_y = -1;
                    } else if (finish_touch(&options, &touch, now)) {
                        stop_requested = 1;
                        break;
                    }
                } else if (event->type == EV_SYN && event->code == SYN_REPORT &&
                           update_touch_position(&options, &x_range, &y_range, &touch, now)) {
                    stop_requested = 1;
                    break;
                }
            }
        }
    }

    release_input();
    return EXIT_SUCCESS;
}
