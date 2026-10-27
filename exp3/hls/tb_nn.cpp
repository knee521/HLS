#include "nn_infer.h"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

// File scores use explicit little-endian encoding, independent of C integer layout.
static int read_score(std::ifstream &stream) {
    unsigned char bytes[4] = {0, 0, 0, 0};
    stream.read(reinterpret_cast<char *>(bytes), 4);
    unsigned int value = unsigned(bytes[0]) | (unsigned(bytes[1]) << 8)
                       | (unsigned(bytes[2]) << 16) | (unsigned(bytes[3]) << 24);
    if (value <= 0x7fffffffU) return int(value);
    return -1 - int(0xffffffffU - value);
}

int main(int argc, char **argv) {
    if (argc != 4) {
        std::fprintf(stderr, "usage: tb_nn VECTOR_DIRECTORY test|cosim OUTPUT_CSV\n");
        return 2;
    }
    const std::string folder = argv[1];
    const std::string mode = argv[2];
    const bool full = mode == "test";
    if (!full && mode != "cosim") return 2;
    const int expected_count = full ? 10000 : 24;
    std::ifstream images((folder + "/" + mode + "_images.bin").c_str(), std::ios::binary);
    std::ifstream scores((folder + "/" + mode + "_scores.bin").c_str(), std::ios::binary);
    std::ifstream labels((folder + "/" + mode + "_labels.bin").c_str(), std::ios::binary);
    std::ofstream output(argv[3]);
    if (!images || !scores || !labels || !output) {
        std::fprintf(stderr, "Cannot open vectors/output\n"); return 2;
    }
    output << "sample_id,label,c_prediction,reference_prediction,score_mismatches\n";
    int correct = 0, disagreements = 0, score_errors = 0;
    for (int n = 0; n < expected_count; ++n) {
        pixel_t input[784];
        unsigned char raw[784];
        images.read(reinterpret_cast<char *>(raw), 784);
        int expected_scores[10];
        for (int k = 0; k < 10; ++k) expected_scores[k] = read_score(scores);
        const int label = labels.get();
        if (!images || !scores || label < 0) { std::fprintf(stderr,"Truncated vectors\n"); return 2; }
        for (int i = 0; i < 784; ++i) input[i] = raw[i];
        const int result = nn_infer(input).to_int();
        int reference = 0;
        for (int k = 1; k < 10; ++k)
            if (expected_scores[k] > expected_scores[reference]) reference = k;
        int local_errors = 0;
        if (full) {
            for (int k = 0; k < 10; ++k)
                if (debug_logits[k] != expected_scores[k]) ++local_errors;
        }
        score_errors += local_errors;
        if (result != reference) ++disagreements;
        if (result == label) ++correct;
        output << n << ',' << label << ',' << result << ',' << reference << ',' << local_errors << '\n';
    }
    if (images.peek() != EOF || scores.peek() != EOF || labels.peek() != EOF) {
        std::fprintf(stderr,"Unexpected extra vectors\n"); return 2;
    }
    std::printf("C_TEST samples=%d correct=%d prediction_mismatches=%d score_mismatches=%d\n",
                expected_count, correct, disagreements, score_errors);
    if (disagreements || score_errors) return 1;
    std::printf("TEST_PASS nn_infer mode=%s\n", mode.c_str());
    return 0;
}

