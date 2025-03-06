#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdbool.h>
#include <ctype.h>
// gcc -shared -o librandomvalues.so -fPIC randomvalues.c

// lastedit: 13.2.2025, alternation added, tested manually

// This C code will break down a regular expression pattern.
// It will then generate random data based on the different broken down tokens.
// Currently supports a subset of relevant regex features for the purpose of this project.
// Supported features can be seen in the token types below.
// Expanding later to support more features should be relatively easy.

typedef enum TokenType TokenType;
typedef enum ASTNodeType ASTNodeType;
typedef struct Token Token;
typedef struct ASTNode ASTNode;
typedef struct CachedAlternatives CachedAlternatives;
void generate_from_node(ASTNode* node, char* buffer, int* output_index);

// These are the types of tokens the regular expression can be broken down into
enum TokenType {
    TOKEN_LITERAL,
    TOKEN_CHAR_CLASS,
    TOKEN_QUANTIFIER,
    TOKEN_ESCAPE,
    TOKEN_ANY_CHAR,
    TOKEN_START,
    TOKEN_END,
    TOKEN_ALTERNATION,
    TOKEN_GROUP
};

// Will build a tree from the tokens that is then looped through to generate random data based on the different nodes
// Not sure if this is ideal, but it does not cost any performance for the current use case, since it is built once per configuration file
// And it is easy to understand and work with
enum ASTNodeType {
    AST_LITERAL,
    AST_CHAR_CLASS,
    AST_QUANTIFIER,
    AST_ESCAPE,
    AST_ANY_CHAR,
    AST_START,
    AST_END,
    AST_ALTERNATION,
    AST_GROUP
};

struct CachedAlternatives {
    Token** tokens;
    int* token_counts;
    ASTNode** roots;
    int num_alternatives;
};

struct Token {
    TokenType type;
    char value[256];
    int min;
    int max;
    bool is_negated;
    char** alternatives;
    int num_alternatives;
    CachedAlternatives* cached_alts;
};

struct ASTNode {
    ASTNodeType type;
    char value[256];
    int min;
    int max;
    bool is_negated;
    struct ASTNode* children;
    int num_children;
    char** alternatives;
    int num_alternatives;
    CachedAlternatives* cached_alts;
};

int tokenize(const char* pattern, Token** tokens, int* num_tokens);
int parse_tokens(Token* tokens, int num_tokens, ASTNode** root);
void free_tokens(Token* tokens);
void free_ast(ASTNode* root);
char* generate_from_pattern(const char* pattern, int max_length);

char random_char_in_range(char start, char end) {
    return start + (rand() % (end - start + 1));
}

char random_digit() {
    return '0' + (rand() % 10);
}

char random_lowercase() {
    return 'a' + (rand() % 26);
}

char random_uppercase() {
    return 'A' + (rand() % 26);
}

char random_alphanumeric() {
    if (rand() % 2 == 0) {
        return random_lowercase();
    } else {
        return random_digit();
    }
}

char random_whitespace() {
    char whitespace_chars[] = {' ', '\t', '\n', '\r'};
    return whitespace_chars[rand() % 4];
}

// Helper function to parse alternatives
int parse_alternative(const char* pattern, int* index, char* buffer) {
    int buf_idx = 0;
    int depth = 0;
    
    while (pattern[*index] != '\0') {
        if (pattern[*index] == '(' && buf_idx > 0) {
            depth++;
        } else if (pattern[*index] == ')') {
            if (depth > 0) {
                depth--;
            } else {
                break;
            }
        } else if (pattern[*index] == '|' && depth == 0) {
            break;
        }
        
        if (buf_idx < 255) {
            buffer[buf_idx++] = pattern[*index];
        }
        (*index)++;
    }
    buffer[buf_idx] = '\0';
    return buf_idx;
}

// Function that breaks down the pattern into tokens
int tokenize(const char* pattern, Token** tokens, int* num_tokens) {
    *tokens = (Token*)calloc(256, sizeof(Token)); // Use calloc instead of malloc
    if (*tokens == NULL) return -1;

    int token_index = 0;
    int pattern_index = 0;

    while (pattern[pattern_index] != '\0') {
        if (pattern[pattern_index] == '\\') {
            // escape sequences
            pattern_index++;
            (*tokens)[token_index].type = TOKEN_ESCAPE;
            (*tokens)[token_index].value[0] = pattern[pattern_index];
            (*tokens)[token_index].value[1] = '\0';
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '[') {
            // character classes
            pattern_index++;
            (*tokens)[token_index].type = TOKEN_CHAR_CLASS;
            (*tokens)[token_index].is_negated = (pattern[pattern_index] == '^');
            if ((*tokens)[token_index].is_negated) {
                pattern_index++;
            }
            int value_index = 0;
            while (pattern[pattern_index] != ']') {
                (*tokens)[token_index].value[value_index++] = pattern[pattern_index++];
            }
            (*tokens)[token_index].value[value_index] = '\0';
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '{') {
            // quantifiers
            pattern_index++; // skip '{'
            (*tokens)[token_index].type = TOKEN_QUANTIFIER;
            
            // extract quantifier content
            char buffer[32];
            int buffer_index = 0;
            while (pattern[pattern_index] != '}' && pattern[pattern_index] != '\0') {
                buffer[buffer_index++] = pattern[pattern_index++];
            }
            buffer[buffer_index] = '\0';
            
            // parse min and max values
            if (strchr(buffer, ',') != NULL) {
                // format: {m,n}
                sscanf(buffer, "%d,%d", &(*tokens)[token_index].min, &(*tokens)[token_index].max);
            } else {
                // format: {n} for exact n matches
                sscanf(buffer, "%d", &(*tokens)[token_index].min);
                (*tokens)[token_index].max = (*tokens)[token_index].min;
            }
            
            token_index++;
            pattern_index++; // skip '}'
        } else if (pattern[pattern_index] == '.') {
            // handle any character
            (*tokens)[token_index].type = TOKEN_ANY_CHAR;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '^') {
            // handle start of string
            (*tokens)[token_index].type = TOKEN_START;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '$') {
            // handle end of string
            (*tokens)[token_index].type = TOKEN_END;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '(' || 
                  (pattern[pattern_index] == '|' && !strchr(pattern, '('))) {
            
            // handle both grouped and bare alternations
            (*tokens)[token_index].type = TOKEN_ALTERNATION;
            (*tokens)[token_index].cached_alts = malloc(sizeof(CachedAlternatives));
            
            // parse alternatives into separate strings
            char buffer[256];
            int num_alts = 0;
            char* alternatives[32] = {NULL};
            
            if (pattern[pattern_index] == '(') {
                pattern_index++; // skip '('
                
                // find all alternatives at current level
                int nested = 1;
                int buf_idx = 0;
                bool has_patterns = false;
                
                // pre process alternatives while checking for regex patterns
                // to handle alternations between different token types
                while (pattern[pattern_index] != '\0' && nested > 0) {
                    if (pattern[pattern_index] == '(') {
                        nested++;
                        buffer[buf_idx++] = pattern[pattern_index];
                        has_patterns = true;
                    } else if (pattern[pattern_index] == ')') {
                        nested--;
                        if (nested > 0) buffer[buf_idx++] = pattern[pattern_index];
                    } else if (pattern[pattern_index] == '\\') {
                        // check for regex escapes
                        if (pattern[pattern_index + 1] == 'd' || 
                            pattern[pattern_index + 1] == 'w' ||
                            pattern[pattern_index + 1] == 's') {
                            has_patterns = true;
                        }
                        buffer[buf_idx++] = pattern[pattern_index++];
                        buffer[buf_idx++] = pattern[pattern_index];
                    } else if (pattern[pattern_index] == '[' || 
                             pattern[pattern_index] == '{') {
                        has_patterns = true;
                        buffer[buf_idx++] = pattern[pattern_index];
                    } else if (pattern[pattern_index] == '|' && nested == 1) {
                        buffer[buf_idx] = '\0';
                        alternatives[num_alts++] = strdup(buffer);
                        buf_idx = 0;
                    } else {
                        buffer[buf_idx++] = pattern[pattern_index];
                    }
                    pattern_index++;
                }
                
                if (buf_idx > 0) {
                    buffer[buf_idx] = '\0';
                    alternatives[num_alts++] = strdup(buffer);
                }
            } else {
                // handle bare alternation (without parentheses)
                (*tokens)[token_index].type = TOKEN_ALTERNATION;
                
                int buf_idx = 0;
                int alt_count = 1;
                
                // count alternatives
                for (int i = 0; pattern[i] != '\0'; i++) {
                    if (pattern[i] == '|') alt_count++;
                }
                
                (*tokens)[token_index].alternatives = (char**)malloc(alt_count * sizeof(char*));
                (*tokens)[token_index].num_alternatives = alt_count;
                
                // parse each alternative
                int alt_idx = 0;
                for (int i = 0; i < pattern_index; i++) {
                    if (buf_idx < 255) buffer[buf_idx++] = pattern[i];
                }
                buffer[buf_idx] = '\0';
                (*tokens)[token_index].alternatives[alt_idx] = strdup(buffer);
                
                alt_idx++;
                buf_idx = 0;
                pattern_index++;  // skipping the |
                
                while (pattern[pattern_index] != '\0') {
                    if (pattern[pattern_index] == '|') {
                        buffer[buf_idx] = '\0';
                        (*tokens)[token_index].alternatives[alt_idx++] = strdup(buffer);
                        buf_idx = 0;
                    } else {
                        if (buf_idx < 255) buffer[buf_idx++] = pattern[pattern_index];
                    }
                    pattern_index++;
                }
                
                if (buf_idx > 0) {
                    buffer[buf_idx] = '\0';
                    (*tokens)[token_index].alternatives[alt_idx] = strdup(buffer);
                }
            }
            
            // pre parse each alternative
            (*tokens)[token_index].cached_alts->num_alternatives = num_alts;
            (*tokens)[token_index].cached_alts->tokens = malloc(num_alts * sizeof(Token*));
            (*tokens)[token_index].cached_alts->token_counts = malloc(num_alts * sizeof(int));
            (*tokens)[token_index].cached_alts->roots = malloc(num_alts * sizeof(ASTNode*));
            
            for (int i = 0; i < num_alts; i++) {
                // parse each alt once and cache the result
                Token* alt_tokens;
                int alt_count;
                if (tokenize(alternatives[i], &alt_tokens, &alt_count) == 0) {
                    ASTNode* alt_root;
                    if (parse_tokens(alt_tokens, alt_count, &alt_root) == 0) {
                        (*tokens)[token_index].cached_alts->tokens[i] = alt_tokens;
                        (*tokens)[token_index].cached_alts->token_counts[i] = alt_count;
                        (*tokens)[token_index].cached_alts->roots[i] = alt_root;
                    }
                }
                free(alternatives[i]); // free original string
            }
            
            token_index++;
        } else {
            // handle literals
            (*tokens)[token_index].type = TOKEN_LITERAL;
            (*tokens)[token_index].value[0] = pattern[pattern_index];
            (*tokens)[token_index].value[1] = '\0';
            token_index++;
            pattern_index++;
        }// add more cases, some might be handled in above cases
    }

    *num_tokens = token_index;
    return 0; // success
}

// parse the tokens into an ast, nodes represent different parts of the regex pattern
int parse_tokens(Token* tokens, int num_tokens, ASTNode** root) {
    printf("Parsing tokens...\n");
    ASTNode* nodes = (ASTNode*)calloc(num_tokens, sizeof(ASTNode)); // using calloc
    if (!nodes) return -1;

    int node_count = 0;
    for (int i = 0; i < num_tokens; ) {
        printf("Processing token %d: type=%d, value='%s'\n", i, tokens[i].type, tokens[i].value);
        
        // initialize all fields of the node
        memset(&nodes[node_count], 0, sizeof(ASTNode));
        nodes[node_count].type = (ASTNodeType)tokens[i].type;
        strncpy(nodes[node_count].value, tokens[i].value, 255);
        nodes[node_count].value[255] = '\0';
        nodes[node_count].min = 1;
        nodes[node_count].max = 1;
        nodes[node_count].is_negated = tokens[i].is_negated;
        nodes[node_count].num_children = 0;
        nodes[node_count].children = NULL;
        nodes[node_count].alternatives = NULL;
        nodes[node_count].num_alternatives = 0;

        if (tokens[i].type == TOKEN_ALTERNATION || 
            (tokens[i].type == TOKEN_GROUP && tokens[i].alternatives != NULL)) {
            printf("Processing alternation with %d alternatives\n", tokens[i].num_alternatives);
            
            if (tokens[i].num_alternatives > 0 && tokens[i].alternatives != NULL) {
                nodes[node_count].alternatives = (char**)calloc(tokens[i].num_alternatives, sizeof(char*));
                if (!nodes[node_count].alternatives) {
                    printf("Failed to allocate alternatives array\n");
                    free(nodes);
                    return -1;
                }
                
                nodes[node_count].num_alternatives = tokens[i].num_alternatives;
                for (int j = 0; j < tokens[i].num_alternatives; j++) {
                    if (tokens[i].alternatives[j]) {
                        nodes[node_count].alternatives[j] = strdup(tokens[i].alternatives[j]);
                        if (!nodes[node_count].alternatives[j]) {
                            printf("Failed to duplicate alternative string\n");
                            // clean previously allocated strings
                            for (int k = 0; k < j; k++) {
                                free(nodes[node_count].alternatives[k]);
                            }
                            free(nodes[node_count].alternatives);
                            free(nodes);
                            return -1;
                        }
                        printf("Copied alternative %d: '%s'\n", j, nodes[node_count].alternatives[j]);
                    }
                }
            }
        }

        if (tokens[i].type == TOKEN_ALTERNATION) {
            // copy the cached alternatives from token to node
            nodes[node_count].cached_alts = tokens[i].cached_alts;
            nodes[node_count].num_alternatives = tokens[i].num_alternatives;
            nodes[node_count].alternatives = tokens[i].alternatives;
            // prevent double-free by nulling token's pointers
            tokens[i].cached_alts = NULL;
            tokens[i].alternatives = NULL;
        }

        // check if next token is a quantifier
        if (i + 1 < num_tokens && tokens[i + 1].type == TOKEN_QUANTIFIER) {
            nodes[node_count].min = tokens[i + 1].min;
            nodes[node_count].max = tokens[i + 1].max;
            printf("Token %d (value='%s') is paired with quantifier token %d (min=%d, max=%d)\n",
                   i, tokens[i].value, i + 1, tokens[i + 1].min, tokens[i + 1].max);
            i += 2;
        } else {
            printf("Token %d (value='%s') is not followed by quantifier\n", i, tokens[i].value);
            i++;
        }
        node_count++;
        printf("Token %d successfully parsed into AST node. Total nodes=%d\n", i, node_count);
    }

    *root = (ASTNode*)calloc(1, sizeof(ASTNode)); // using calloc
    if (!*root) {
        free(nodes);
        return -1;
    }
    (*root)->type = AST_GROUP;
    (*root)->num_children = node_count;
    (*root)->children = (ASTNode*)malloc(node_count * sizeof(ASTNode));
    if (!(*root)->children) {
        free(nodes);
        free(*root);
        *root = NULL;
        return -1;
    }
    memcpy((*root)->children, nodes, node_count * sizeof(ASTNode));
    free(nodes);

    return 0;
}

void free_ast(ASTNode* root) {
    if (!root) return;
    
    printf("Freeing AST\n");
    if (root->children) {
        for (int i = 0; i < root->num_children; i++) {
            // free cached alternatives first
            if (root->children[i].cached_alts) {
                for (int j = 0; j < root->children[i].cached_alts->num_alternatives; j++) {
                    if (root->children[i].cached_alts->roots[j]) {
                        free_ast(root->children[i].cached_alts->roots[j]);
                    }
                    if (root->children[i].cached_alts->tokens[j]) {
                        free_tokens(root->children[i].cached_alts->tokens[j]);
                    }
                }
                free(root->children[i].cached_alts->roots);
                free(root->children[i].cached_alts->tokens);
                free(root->children[i].cached_alts->token_counts);
                free(root->children[i].cached_alts);
            }
            if (root->children[i].alternatives) {
                printf("Freeing AST node alternatives: %d\n", root->children[i].num_alternatives);
                if (root->children[i].num_alternatives > 0) {
                    for (int j = 0; j < root->children[i].num_alternatives; j++) {
                        if (root->children[i].alternatives[j]) {
                            printf("Freeing alternative %d: '%s'\n", j, root->children[i].alternatives[j]);
                            free(root->children[i].alternatives[j]);
                        }
                    }
                }
                free(root->children[i].alternatives);
                root->children[i].alternatives = NULL;
            }
        }
        free(root->children);
    }
    free(root);
}

void free_tokens(Token* tokens) {
    if (!tokens) return;
    
    printf("Freeing tokens\n");
    for (int i = 0; i < 256; i++) { // fixed size since we allocated 256
        if (tokens[i].type == TOKEN_ALTERNATION && tokens[i].alternatives) {
            printf("Freeing token alternatives: %d\n", tokens[i].num_alternatives);
            for (int j = 0; j < tokens[i].num_alternatives; j++) {
                if (tokens[i].alternatives[j]) {
                    free(tokens[i].alternatives[j]);
                }
            }
            free(tokens[i].alternatives);
        }
        if (tokens[i].type == 0) break; // stop at first empty token
    }
    free(tokens);
}

// Random seed initialization
void initialize_random() {
    srand(time(NULL));
}

// generates random data based on the patterns
// parameters are related to the use case of this project, they are handled in the python code
int generate_all_data(char** headers, char** patterns, int num_headers,
                      int rows, char*** out_data) {
    *out_data = (char**)malloc(rows * num_headers * sizeof(char*));
    if (!*out_data) return -1;

    Token** token_array = (Token**)malloc(num_headers * sizeof(Token*));
    int* token_counts = (int*)malloc(num_headers * sizeof(int));
    ASTNode** ast_array = (ASTNode**)malloc(num_headers * sizeof(ASTNode*));
    if (!token_array || !token_counts || !ast_array) return -1;

    for (int i = 0; i < num_headers; i++) {
        token_array[i] = NULL;
        token_counts[i] = 0;
        
        // for alternations, validate each alternative is a complete pattern
        if (strchr(patterns[i], '|')) {
            char* pattern_copy = strdup(patterns[i]);
            char* alt = strtok(pattern_copy, "|");
            while (alt) {
                // trim whitespaces
                while (*alt == ' ') alt++;
                char* end = alt + strlen(alt) - 1;
                while (end > alt && *end == ' ') end--;
                *(end + 1) = '\0';
                
                // validate each alternative produces valid tokens
                Token* test_tokens = NULL;
                int test_count = 0;
                if (tokenize(alt, &test_tokens, &test_count) != 0) {
                    free(pattern_copy);
                    // Cleanup and return error
                    return -1;
                }
                free_tokens(test_tokens);
                alt = strtok(NULL, "|");
            }
            free(pattern_copy);
        }
        
        if (tokenize(patterns[i], &token_array[i], &token_counts[i]) != 0) {
            // cleanup previous allocations
            for (int j = 0; j < i; j++) {
                if (ast_array[j]) free_ast(ast_array[j]);
                if (token_array[j]) free_tokens(token_array[j]);
            }
            free(token_array);
            free(token_counts);
            free(ast_array);
            return -1;
        }
        ast_array[i] = NULL;
        if (parse_tokens(token_array[i], token_counts[i], &ast_array[i]) != 0) {
            return -1;
        }
    }

    // generate random data for each pattern, 
    for (int r = 0; r < rows; r++) {
        for (int h = 0; h < num_headers; h++) {
            char* buffer = (char*)malloc(256);
            if (!buffer) return -1;
            int output_index = 0;
            ASTNode* root = ast_array[h];
            for (int i = 0; i < root->num_children; i++) {
                ASTNode* node = &root->children[i];
                int length = (node->min == node->max)
                    ? node->min
                    : node->min + (rand() % (node->max - node->min + 1));
                for (int j = 0; j < length && output_index < 255; j++) {
                    switch (node->type) {
                        case AST_LITERAL:
                            buffer[output_index++] = node->value[0];
                            break;
                        case AST_CHAR_CLASS:
                            if (node->is_negated) {
                                char c;
                                do {
                                    c = random_char_in_range(' ', '~');
                                } while (strchr(node->value, c) != NULL);
                                buffer[output_index++] = c;
                            } else {
                                char start = node->value[0];
                                char end = node->value[2];
                                buffer[output_index++] = random_char_in_range(start, end);
                            }
                            break;
                        case AST_ESCAPE:
                            switch (node->value[0]) {
                                case 'd':
                                    buffer[output_index++] = random_digit();
                                    break;
                                case 'w':
                                    buffer[output_index++] = random_alphanumeric();
                                    break;
                                case 's':
                                    buffer[output_index++] = random_whitespace();
                                    break;
                                default:
                                    buffer[output_index++] = node->value[0];
                                    break;
                            }
                            break;
                        case AST_ANY_CHAR:
                            buffer[output_index++] = random_char_in_range(' ', '~');
                            break;
                        case AST_ALTERNATION: {
                            if (node->cached_alts && node->cached_alts->roots) {
                                int alt_idx = rand() % node->cached_alts->num_alternatives;
                                ASTNode* alt_root = node->cached_alts->roots[alt_idx];
                                
                                if (alt_root) {
                                    for (int k = 0; k < alt_root->num_children; k++) {
                                        ASTNode* alt_node = &alt_root->children[k];
                                        int alt_len = (alt_node->min == alt_node->max)
                                            ? alt_node->min
                                            : alt_node->min + (rand() % (alt_node->max - alt_node->min + 1));
                                            
                                        for (int l = 0; l < alt_len && output_index < 255; l++) {
                                            generate_from_node(alt_node, buffer, &output_index);
                                        }
                                    }
                                }
                            }
                            break;
                        }
                        default:
                            break;
                    }
                }
            }
            buffer[output_index] = '\0';
            (*out_data)[r*num_headers + h] = buffer;
        }
    }

    // free ASTs & tokens
    for (int i = 0; i < num_headers; i++) {
        free_ast(ast_array[i]);
        free_tokens(token_array[i]);
    }
    free(token_array);
    free(token_counts);
    free(ast_array);

    return 0;
}
// using this in the above function, 
void generate_from_node(ASTNode* node, char* buffer, int* output_index) {
    switch (node->type) {
        case AST_LITERAL:
            buffer[*output_index] = node->value[0];
            (*output_index)++;
            break;
            
        case AST_ESCAPE:
            switch (node->value[0]) {
                case 'd':
                    buffer[*output_index] = random_digit();
                    (*output_index)++;
                    break;
                case 'w':
                    buffer[*output_index] = random_alphanumeric();
                    (*output_index)++;
                    break;
                case 's':
                    buffer[*output_index] = random_whitespace();
                    (*output_index)++;
                    break;
                default:
                    buffer[*output_index] = node->value[0];
                    (*output_index)++;
                    break;
            }
            break;
            
        case AST_CHAR_CLASS:
            if (node->is_negated) {
                char c;
                do {
                    c = random_char_in_range(' ', '~');
                } while (strchr(node->value, c) != NULL);
                buffer[*output_index] = c;
            } else {
                char start = node->value[0];
                char end = node->value[2];
                buffer[*output_index] = random_char_in_range(start, end);
            }
            (*output_index)++;
            break;
            
        case AST_ANY_CHAR:
            buffer[*output_index] = random_char_in_range(' ', '~');
            (*output_index)++;
            break;
            
        case AST_ALTERNATION:
            if (node->alternatives && node->num_alternatives > 0) {
                int alt_idx = rand() % node->num_alternatives;
                const char* alt = node->alternatives[alt_idx];
                int len = strlen(alt);
                if (*output_index + len < 255) {
                    memcpy(buffer + *output_index, alt, len);
                    *output_index += len;
                }
            }
            break;
    }
}

// Function to generate a random value from a single AST node for pattern previews
int generate_random_value_from_ast(ASTNode* root, char* buffer, int max_length) {
    int output_index = 0;
    buffer[0] = '\0';
    
    if (!root) return -1;
    
    // process all nodes at this level
    for (int i = 0; i < root->num_children && output_index < max_length - 1; i++) {
        ASTNode* node = &root->children[i];
        
    // calculate repetition count based on quantifiers
        int length = (node->min == node->max) 
                    ? node->min 
                    : node->min + (rand() % (node->max - node->min + 1));
            
    // generate values according to node type
        for (int j = 0; j < length && output_index < max_length - 1; j++) {
            switch (node->type) {
                case AST_LITERAL:
                    buffer[output_index++] = node->value[0];
                    break;
                    
                case AST_CHAR_CLASS:
                    if (node->is_negated) {
                        char c;
                        do {
                            c = random_char_in_range(' ', '~');
                        } while (strchr(node->value, c) != NULL);
                        buffer[output_index++] = c;
                    } else {
                        char start = node->value[0];
                        char end = node->value[2];
                        buffer[output_index++] = random_char_in_range(start, end);
                    }
                    break;
                    
                case AST_ESCAPE:
                    switch (node->value[0]) {
                        case 'd':
                            buffer[output_index++] = random_digit();
                            break;
                        case 'w':
                            buffer[output_index++] = random_alphanumeric();
                            break;
                        case 's':
                            buffer[output_index++] = random_whitespace();
                            break;
                        default:
                            buffer[output_index++] = node->value[0];
                            break;
                    }
                    break;
                    
                case AST_ANY_CHAR:
                    buffer[output_index++] = random_char_in_range(' ', '~');
                    break;
                    
                case AST_ALTERNATION: {
                    if (node->cached_alts && node->cached_alts->num_alternatives > 0) {
                        int alt_idx = rand() % node->cached_alts->num_alternatives;
                        ASTNode* alt_root = node->cached_alts->roots[alt_idx];
                        
                        // process all nodes in the chosen alternative
                        if (alt_root) {
                            for (int k = 0; k < alt_root->num_children; k++) {
                                ASTNode* alt_node = &alt_root->children[k];
                                int alt_len = (alt_node->min == alt_node->max)
                                    ? alt_node->min
                                    : alt_node->min + (rand() % (alt_node->max - alt_node->min + 1));
                                
                                for (int l = 0; l < alt_len && output_index < max_length - 1; l++) {
                                    generate_from_node(alt_node, buffer, &output_index);
                                }
                            }
                        }
                    }
                    // fall back to alternatives array if cached_alts isn't available
                    else if (node->alternatives && node->num_alternatives > 0) {
                        int alt_idx = rand() % node->num_alternatives;
                        const char* alt = node->alternatives[alt_idx];
                        if (alt) {
                            int len = strlen(alt);
                            if (output_index + len < max_length) {
                                memcpy(buffer + output_index, alt, len);
                                output_index += len;
                            }
                        }
                    }
                    // Debug if no alternatives found
                    else {
                        const char* err_msg = "[ALT_ERROR]";
                        int len = strlen(err_msg);
                        if (output_index + len < max_length) {
                            memcpy(buffer + output_index, err_msg, len);
                            output_index += len;
                        }
                    }
                    break;
                }
                
                default:
                    break;
            }
        }
    }
    
    buffer[output_index] = '\0';
    return 0;
}