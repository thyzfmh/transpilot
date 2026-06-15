//! Rust 翻译: 并发 Worker Pool 模式
//! 
//! 翻译决策:
//! - goroutine worker → std::thread::spawn (CPU 密集型，避免阻塞 tokio)
//! - chan Job → crossbeam::channel (多生产者多消费者)
//! - context.Done() → CancellationToken
//! - sync.WaitGroup → JoinHandle 集合
//! - []Result → Vec<Result>

use std::fmt;
use std::thread;
use crossbeam_channel::{bounded, Sender, Receiver};
use tokio_util::sync::CancellationToken;

#[derive(Debug, Clone)]
pub struct Job {
    pub id: i32,
    pub data: String,
}

#[derive(Debug)]
pub struct JobResult {
    pub job_id: i32,
    pub output: String,
    pub error: Option<String>,
}

pub fn process_jobs(
    cancel: &CancellationToken,
    jobs: Vec<Job>,
    worker_count: usize,
) -> Vec<JobResult> {
    let (job_tx, job_rx): (Sender<Job>, Receiver<Job>) = bounded(jobs.len());
    let (result_tx, result_rx): (Sender<JobResult>, Receiver<JobResult>) = bounded(jobs.len());

    // 启动 workers
    let mut handles = Vec::with_capacity(worker_count);
    for worker_id in 0..worker_count {
        let job_rx = job_rx.clone();
        let result_tx = result_tx.clone();
        let cancel = cancel.clone();

        let handle = thread::spawn(move || {
            for job in job_rx.iter() {
                if cancel.is_cancelled() {
                    let _ = result_tx.send(JobResult {
                        job_id: job.id,
                        output: String::new(),
                        error: Some("cancelled".to_string()),
                    });
                    return;
                }
                let output = format!("worker-{} processed: {}", worker_id, job.data);
                let _ = result_tx.send(JobResult {
                    job_id: job.id,
                    output,
                    error: None,
                });
            }
        });
        handles.push(handle);
    }

    // 发送 jobs
    for job in jobs {
        let _ = job_tx.send(job);
    }
    drop(job_tx); // close channel

    // 等待所有 worker 完成
    for handle in handles {
        let _ = handle.join();
    }
    drop(result_tx); // 所有发送端关闭后 result_rx 会结束迭代

    // 收集结果
    result_rx.iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_process_jobs() {
        let cancel = CancellationToken::new();
        let jobs = vec![
            Job { id: 1, data: "hello".to_string() },
            Job { id: 2, data: "world".to_string() },
        ];

        let results = process_jobs(&cancel, jobs, 2);
        assert_eq!(results.len(), 2);
        assert!(results.iter().all(|r| r.error.is_none()));
    }

    #[test]
    fn test_cancellation() {
        let cancel = CancellationToken::new();
        cancel.cancel(); // 立即取消

        let jobs = vec![Job { id: 1, data: "test".to_string() }];
        let results = process_jobs(&cancel, jobs, 1);
        assert!(results.iter().any(|r| r.error.is_some()));
    }
}
