//! Rust 翻译: 双向链表（索引方案）
//!
//! 翻译决策:
//! - 侵入式链表 → 索引方案（NodePool + NodeId）
//!   原因: 避免 unsafe，避免生命周期复杂性
//! - malloc/free → Vec 自动管理
//! - NULL 指针 → Option<NodeId>
//! - char[64] → String（Rust 无需固定缓冲区）
//! - 返回指针 → 返回 NodeId
//!
//! 重要: 这不是逐行翻译，而是语义等价的 Rust 惯用实现

use std::collections::HashMap;

/// 节点标识符（newtype 防止误用）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId(usize);

/// 节点数据
#[derive(Debug, Clone)]
struct NodeData {
    key: i32,
    value: String,
    next: Option<NodeId>,
    prev: Option<NodeId>,
}

/// 双向链表（索引方案，全 safe）
#[derive(Debug)]
pub struct LinkedList {
    nodes: Vec<Option<NodeData>>,  // None = 已删除的槽位
    head: Option<NodeId>,
    tail: Option<NodeId>,
    count: usize,
    free_slots: Vec<usize>,  // 回收已删除的槽位
}

impl LinkedList {
    /// 对应 list_create
    pub fn new() -> Self {
        Self {
            nodes: Vec::new(),
            head: None,
            tail: None,
            count: 0,
            free_slots: Vec::new(),
        }
    }

    /// 对应 list_push_back
    pub fn push_back(&mut self, key: i32, value: &str) -> NodeId {
        let node = NodeData {
            key,
            value: value.to_string(),
            next: None,
            prev: self.tail,
        };

        // 分配槽位（优先复用已释放的）
        let id = if let Some(slot) = self.free_slots.pop() {
            self.nodes[slot] = Some(node);
            NodeId(slot)
        } else {
            let slot = self.nodes.len();
            self.nodes.push(Some(node));
            NodeId(slot)
        };

        // 更新链接
        if let Some(tail_id) = self.tail {
            if let Some(tail_node) = &mut self.nodes[tail_id.0] {
                tail_node.next = Some(id);
            }
        } else {
            self.head = Some(id);
        }
        self.tail = Some(id);
        self.count += 1;
        id
    }

    /// 对应 list_find
    pub fn find(&self, key: i32) -> Option<NodeId> {
        let mut current = self.head;
        while let Some(id) = current {
            if let Some(node) = &self.nodes[id.0] {
                if node.key == key {
                    return Some(id);
                }
                current = node.next;
            } else {
                break;
            }
        }
        None
    }

    /// 对应 list_remove
    pub fn remove(&mut self, id: NodeId) -> bool {
        let (prev, next) = match &self.nodes[id.0] {
            Some(node) => (node.prev, node.next),
            None => return false,  // 已删除
        };

        // 更新前驱的 next
        if let Some(prev_id) = prev {
            if let Some(prev_node) = &mut self.nodes[prev_id.0] {
                prev_node.next = next;
            }
        } else {
            self.head = next;
        }

        // 更新后继的 prev
        if let Some(next_id) = next {
            if let Some(next_node) = &mut self.nodes[next_id.0] {
                next_node.prev = prev;
            }
        } else {
            self.tail = prev;
        }

        // 释放槽位
        self.nodes[id.0] = None;
        self.free_slots.push(id.0);
        self.count -= 1;
        true
    }

    /// 获取节点值
    pub fn get(&self, id: NodeId) -> Option<(&i32, &str)> {
        self.nodes[id.0].as_ref().map(|n| (&n.key, n.value.as_str()))
    }

    /// 获取长度
    pub fn len(&self) -> usize {
        self.count
    }

    pub fn is_empty(&self) -> bool {
        self.count == 0
    }
}

// 对应 list_destroy — Rust 通过 Drop 自动处理
impl Drop for LinkedList {
    fn drop(&mut self) {
        // Vec<Option<NodeData>> 自动释放所有内存
        // 无需手动遍历释放
    }
}

impl Default for LinkedList {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_push_and_find() {
        let mut list = LinkedList::new();
        list.push_back(1, "hello");
        list.push_back(2, "world");
        list.push_back(3, "rust");

        assert_eq!(list.len(), 3);
        
        let found = list.find(2);
        assert!(found.is_some());
        let (key, val) = list.get(found.unwrap()).unwrap();
        assert_eq!(*key, 2);
        assert_eq!(val, "world");
    }

    #[test]
    fn test_remove() {
        let mut list = LinkedList::new();
        let id1 = list.push_back(1, "a");
        let id2 = list.push_back(2, "b");
        let id3 = list.push_back(3, "c");

        list.remove(id2);
        assert_eq!(list.len(), 2);
        assert!(list.find(2).is_none());
        assert!(list.find(1).is_some());
        assert!(list.find(3).is_some());
    }

    #[test]
    fn test_remove_head_tail() {
        let mut list = LinkedList::new();
        let id1 = list.push_back(1, "first");
        let id2 = list.push_back(2, "last");

        list.remove(id1); // remove head
        assert_eq!(list.len(), 1);
        
        list.remove(id2); // remove tail (now also head)
        assert!(list.is_empty());
    }

    #[test]
    fn test_slot_reuse() {
        let mut list = LinkedList::new();
        let id1 = list.push_back(1, "a");
        list.remove(id1);
        
        // 新节点应复用已释放的槽位
        let id2 = list.push_back(2, "b");
        assert_eq!(id2.0, id1.0); // 同一个槽位
    }
}
