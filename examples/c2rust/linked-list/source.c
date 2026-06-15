// C 源代码: 侵入式双向链表
#include <stdlib.h>
#include <string.h>

typedef struct node {
    struct node *next;
    struct node *prev;
    int key;
    char value[64];
} node_t;

typedef struct list {
    node_t *head;
    node_t *tail;
    int count;
} list_t;

list_t *list_create(void) {
    list_t *list = calloc(1, sizeof(list_t));
    return list;
}

void list_destroy(list_t *list) {
    node_t *current = list->head;
    while (current) {
        node_t *next = current->next;
        free(current);
        current = next;
    }
    free(list);
}

node_t *list_push_back(list_t *list, int key, const char *value) {
    node_t *node = malloc(sizeof(node_t));
    if (!node) return NULL;
    
    node->key = key;
    strncpy(node->value, value, sizeof(node->value) - 1);
    node->value[sizeof(node->value) - 1] = '\0';
    node->next = NULL;
    node->prev = list->tail;
    
    if (list->tail) {
        list->tail->next = node;
    } else {
        list->head = node;
    }
    list->tail = node;
    list->count++;
    return node;
}

node_t *list_find(list_t *list, int key) {
    node_t *current = list->head;
    while (current) {
        if (current->key == key) return current;
        current = current->next;
    }
    return NULL;
}

void list_remove(list_t *list, node_t *node) {
    if (node->prev) node->prev->next = node->next;
    else list->head = node->next;
    
    if (node->next) node->next->prev = node->prev;
    else list->tail = node->prev;
    
    list->count--;
    free(node);
}
